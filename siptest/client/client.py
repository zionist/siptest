import logging
import dpkt
from twisted.internet import reactor, protocol
from twisted.internet.protocol import DatagramProtocol
from collections import OrderedDict

from siptest.common.constants import SDP_DATA
from siptest.sip import SipMessage


class RtpClient(DatagramProtocol):
    """
    Basic RTP client for both legs. Reads packages from file
    """

    def __init__(self, host, port, options):
        self.host = host
        self.port = port
        self.options = options
        self.logger = logging.getLogger()

    def stopProtocol(self):
        pass

    def startProtocol(self):
        self.transport.connect(self.host, self.port)
        reactor.callLater(1, self.sendDatagram)

    def sendDatagram(self):
        with open(self.options.rtp_file) as f:
            pcap = dpkt.pcap.Reader(f)
            # secs = 0.1
            for ts, buf in pcap:
                eth = dpkt.ethernet.Ethernet(buf)
                ip = eth.data
                udp = ip.data
                # reactor.callLater(secs, self.transport.write, udp.data)
                try:
                    self.transport.write(udp.data)
                except Exception:
                    self.logger.warning("Can't write to UDP socket")
                    pass
                # secs += 0.1

    def datagramReceived(self, datagram, host):
        self.logger.debug("RTP data received %s" % len(datagram))


class TwistedBaseClient(protocol.Protocol):
    """
    Common class for sip Sender and Receiver
    """

    def register(self):
        """
        Send sip registration message
        """
        headers = {
            'CSeq': '1 REGISTER',
            'Via': 'SIP/2.0/TCP 82.144.65.34;branch=%(branch)s;rport',
            'User-Agent': 'TestAgent/4.0.1',
            'From': '<sip:%(msisdn)s@%(domain)s>;tag=%(tag)s',
            'To': '<sip:%(msisdn)s@%(domain)s>',
            'Contact':  '<sip:%(msisdn)s@%(domain)s;transport=tcp>',
            'Expires': '3600',
            'Call-ID': '%(call_id)s',
            'Content-Length': '0',
        }
        for key, value in headers.items():
            headers[key] = value % self.factory.to_dict()
        req = SipMessage(method="REGISTER", headers=headers, is_request=True)
        self.factory.messages['register_no_auth'] = req
        self.do_request(req)
        # self.factory.logger.info("Registration done %s" % self.factory)

    def connectionMade(self):
        self.register()

    def send_deferred(self, msg, seconds):
        reactor.callLater(seconds, self.do_request, msg)

    def do_request(self, msg):
        self.factory.log(msg, send=True)
        self.transport.write(msg.gen_sip_message)
        self.factory.requests_done += 1

    def dataReceived(self, data):
        """
        Get answer against REGISTER request, count digest and make registration
        """
        self.factory.responses_received += 1
        resps = SipMessage.parse(data)
        for res in resps:
            self.factory.log(res, send=False)
        if self.factory.registration_done:
            return
        for res in resps:
            if not res.is_request and res.status == 407 \
                    and "REGISTER" in res.headers.get("CSeq"):
                req = self.factory.messages['register_no_auth'].copy()
                client_header = req.gen_auth_header(
                    res.headers.get("Proxy-Authenticate", ""),
                    self.factory.msisdn,
                    self.factory.password
                )
                req.headers.update(client_header)
                req.headers["CSeq"] = "2 REGISTER"
                self.do_request(req)
            if not res.is_request and res.status == 200 \
                    and "REGISTER" in res.headers.get("CSeq"):
                self.factory.registration_done = True

    def connectionLost(self, reason):
        pass

    def defered_register(self, seconds):
        reactor.callLater(seconds, self.register)


class Sender(TwistedBaseClient):

    # start Sender after Receiver
    def connectionMade(self):
        # self.factory.logger.info("Connection made %s" % self.factory)
        self.defered_register(10)
        # self.register()

    def dataReceived(self, data):
        TwistedBaseClient.dataReceived(self, data)
        # must be registred for doing call
        if not self.factory.registration_done:
            return
        # receiver can get any count of sip packages in one tcp message
        resps = SipMessage.parse(data)
        for res in resps:
            # do nothing on 180 ringing
            if not res.is_request and res.status == 180 \
                    and res.method == "INVITE":
                return
            # disconnect
            if not res.is_request and res.method == "BYE" \
                    and res.status == 200:
                self.factory.successes += 1
                self.factory.active_calls -= 1
                self.transport.loseConnection()
            # got timeout from server for call
            if res.is_request and res.method == "BYE":
                headers = {}
                res_headers = {}
                res_headers.update(res.headers)
                for header_name in ["Via", "To", "From", "Call-ID", "CSeq",
                                    "Content-Length"]:
                    headers[header_name] = res_headers[header_name]
                    res = SipMessage(status=200, is_request=False, method="BYE",
                                     headers=headers)
                self.do_request(res)
                if self.factory.call_connected:
                    self.factory.successes += 1
                    self.factory.active_calls -= 1
                    self.transport.loseConnection()
            if not res.is_request and res.method == "INVITE" and res.status==200:
                pass
                # TODO: add ability to answer for 200 ok with SDP for long calls
                # headers = {}
                # for header_name in ["Via", "From", "To", "Call-ID",
                #                    "CSeq", "Contact"]:
                #     headers[header_name] = res.headers[header_name]
                # headers["Content-Length"] = "0"
                # headers["Max-Forwards"] = "70"
                # method = "ACK"
                # req = SipMessage(is_request=True, method=method,
                #                 headers=headers, to=self.factory.to)
                # self.do_request(req)
            if self.factory.call_connected:
                return
            if not res.is_request and res.status == 200 \
                    and res.method == "INVITE":
                # get RTP connection properties, connect rtp fake rtp client
                self.factory.connect_udp(*self.factory.parse_sdp(res))
                self.factory.call_connected = True
                self.factory.active_calls += 1
                # wait for end of call
                headers = {}
                for header_name in ["Via", "From", "To", "Call-ID"]:
                    headers[header_name] = res.headers[header_name]
                headers["Content-Length"] = "0"
                method = "ACK"
                headers["CSeq"] = "4 ACK"
                req = SipMessage(is_request=True, method=method,
                                 headers=headers)
                # self.do_request(req)
                # self.send_deferred_bye(req, self.factory.options.duration)
                method = "BYE"
                headers["CSeq"] = "4 BYE"
                req = SipMessage(is_request=True, method=method,
                                 headers=headers)
                # wait then send for non blocking purposes
                self.send_deferred(req, self.factory.options.duration + 1)
            if self.factory.call_connected:
                return
            if not res.status == 100 and not res.status == 407:
                # send first INVITE. Resend if smth goes wrong
                # count sent INVITES
                self.factory.invites_count += 1
                # generate new Call-ID and tag
                self.factory.new_call()
                data = SDP_DATA % self.factory.to_dict()
                headers = OrderedDict()
                headers.update({
                    'Via': 'SIP/2.0/TCP 82.144.65.34;branch=%(branch)s;rport',
                    'From': '<sip:%(msisdn)s@%(domain)s>;tag=%(tag)s',
                    'To': '<sip:*%(to)s@%(domain)s>',
                    'CSeq': '1 INVITE',
                    'Call-ID': '%(call_id)s',
                    'Max-Forwards': '70',
                    'Supported': 'replaces, outbound',
                    'Allow': 'INVITE, ACK, CANCEL, OPTIONS, BYE, REFER, '
                             'NOTIFY, MESSAGE, SUBSCRIBE, INFO',
                    'Content-Type': "application/sdp",
                    'Content-Length': "%s" % len(data),
                    'Contact':  '<sip:%(msisdn)s@%(domain)s;transport=tcp>',
                    'User-Agent': 'TestAgent/4.0.1',
                })
                for key, value in headers.items():
                    headers[key] = value % self.factory.to_dict()
                req = SipMessage(method="INVITE",
                                 headers=headers,
                                 body=data,
                                 is_request=True,
                                 to=self.factory.to)
                self.factory.log(req, send=True)
                self.do_request(req)
                # self.send_deferred(req, 20)
                # self.send_deferred(req, 20)
                self.factory.messages["invite_no_auth"] = req
            # send INVITE with digest
            elif res.status == 407 and "INVITE" in res.headers.get("CSeq"):
                # ACK
                # headers = {}
                # for header_name in ["Via", "From", "To", "Call-ID", ]:
                #     headers[header_name] = res.headers[header_name]
                # headers["Content-Length"] = "0"
                # headers["CSeq"] = "3 ACK"
                # method = "ACK"
                # req = SipMessage(is_request=True, method=method,
                #                 headers=headers, to=self.factory.to)
                # self.do_request(req)
                #  self.factory.log(res)
                req = self.factory.messages['invite_no_auth'].copy()
                client_header = req.gen_auth_header(
                    res.headers.get("Proxy-Authenticate", ""),
                    self.factory.msisdn,
                    self.factory.password
                )
                req.headers.update(client_header)
                req.headers["CSeq"] = "2 INVITE"
                self.do_request(req)


class Receiver(TwistedBaseClient):

    def connectionMade(self):
        # self.factory.logger.info("Connection made %s" % self.factory)
        # self.factory.call_connected = False
        # self.factory.new_call()
        # run receivers one by one
        self.register()
        #delay = self.factory.options.interval * self.factory.num
        # self.defered_register(self.factory.interval)

    def dataReceived(self, data):
        TwistedBaseClient.dataReceived(self, data)
        msg = SipMessage.parse(data)[0]
        if msg.is_request and msg.method == "INVITE":
            # get RTP connection properties, connect rtp fake rtp client
            self.factory.connect_udp(*self.factory.parse_sdp(msg))
            headers = {}
            for header_name in ["Via", "From", "To", "Call-ID", "CSeq"]:
                headers[header_name] = msg.headers[header_name]
            headers["Content-Length"] = "0"
            method = "INVITE"
            res = SipMessage(status=100, is_request=False, method=method,
                             headers=headers)
            self.do_request(res)
            res = SipMessage(status=180, is_request=False, method=method,
                             headers=headers)
            self.do_request(res)
            headers["Content-Type"] = "application/sdp"
            data = SDP_DATA % self.factory.to_dict()
            headers["Content-Length"] = len(data)
            res = SipMessage(status=200, body=data,
                             is_request=False, method=method, headers=headers)
            self.do_request(res)
        elif msg.is_request and msg.method == "BYE":
            headers = {}
            for header_name in ["Via", "From", "To", "Call-ID", "CSeq",
                                "Content-Length"]:
                headers[header_name] = msg.headers[header_name]
                res = SipMessage(status=200, is_request=False, method="BYE",
                                 headers=headers)
            self.do_request(res)
            self.factory.successes += 1
            self.transport.loseConnection()
