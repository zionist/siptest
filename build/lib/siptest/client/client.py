import time
from twisted.internet import reactor, protocol
import datetime
from collections import OrderedDict

from siptest.common.constants import SDP_DATA
from siptest.sip import SipMessage


class TwistedBaseClient(protocol.Protocol):
    """
    Common class for sip Sender and Receiver
    """

    def register(self):
        """
        Send sip registration message
        """
        self.factory.runs += 1
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
            headers[key] = value % self.factory.to_dict
        req = SipMessage(method="REGISTER", headers=headers, is_request=True)
        self.factory.messages['register_no_auth'] = req
        self.transport.write(req.gen_sip_message)

    def connectionMade(self):
        self.factory.new_call()
        self.register()

    def send_deferred(self, msg, seconds):
        def f(msg, seconds):
            time.sleep(seconds)
            self.factory.log(msg, send=True)
            self.transport.write(msg.gen_sip_message)

        reactor.callInThread(f, msg, seconds)

    def dataReceived(self, data):
        """
        Get answer against REGISTER request, count digest and make registration
        """
        if self.factory.registration_done:
            return
        resps = SipMessage.parse(data)
        for res in resps:
            self.factory.log(res, send=False)
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
                self.factory.log(req, send=True)
                self.transport.write(req.gen_sip_message)
            if not res.is_request and res.status == 200 \
                    and "REGISTER" in res.headers.get("CSeq"):
                self.factory.registration_done = True

    def connectionLost(self, reason):
        pass
        # print("connection lost")

    def defered_register(self, seconds):
        time.sleep(seconds)
        reactor.callInThread(self.register)


class Sender(TwistedBaseClient):

    # start Sender after Receiver
    def connectionMade(self):
        self.factory.call_connected = False
        self.factory.new_call()
        delay = self.factory.options.interval * self.factory.num + 5
        self.defered_register(delay)

    def dataReceived(self, data):
        super(Sender, self).dataReceived(data)
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
                self.transport.loseConnection()
            if self.factory.call_connected:
                return
            if not res.is_request and res.status == 200 \
                    and res.method == "INVITE":
                self.factory.call_connected = True
                # wait for end of call
                headers = {}
                for header_name in ["Via", "From", "To", "Call-ID"]:
                    headers[header_name] = res.headers[header_name]
                headers["Content-Length"] = "0"
                method = "ACK"
                headers["CSeq"] = "3 ACK"
                req = SipMessage(is_request=True, method=method,
                                 headers=headers)
                self.factory.log(req, send=True)
                self.transport.write(req.gen_sip_message)
                method = "BYE"
                headers["CSeq"] = "4 BYE"
                req = SipMessage(is_request=True, method=method,
                                 headers=headers)
                # wait then send for non blocking purposes
                self.send_deferred(req, self.factory.options.duration)
            # send first INVITE. Resend if smth goes wrong
            if self.factory.call_connected:
                return
            if not res.status == 100 and not res.status == 407:
                # generate new Call-ID and tag
                self.factory.new_call()
                data = SDP_DATA % self.factory.to_dict
                headers = OrderedDict()
                headers.update({
                    'Via': 'SIP/2.0/TCP 82.144.65.34;branch=%(branch)s;rport',
                    'From': '<sip:%(msisdn)s@%(domain)s>;tag=%(tag)s',
                    'To': '<sip:%(to)s@%(domain)s>',
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
                    headers[key] = value % self.factory.to_dict
                req = SipMessage(method="INVITE",
                                 headers=headers,
                                 body=data,
                                 is_request=True,
                                 to=self.factory.to)
                self.factory.log(req, send=True)
                self.transport.write(req.gen_sip_message)
                self.factory.messages["invite_no_auth"] = req
            # send INVITE with digest
            elif res.status == 407 and "INVITE" in res.headers.get("CSeq"):
                req = self.factory.messages['invite_no_auth'].copy()
                client_header = req.gen_auth_header(
                    res.headers.get("Proxy-Authenticate", ""),
                    self.factory.msisdn,
                    self.factory.password
                )
                req.headers.update(client_header)
                req.headers["CSeq"] = "2 INVITE"
                self.factory.log(req, send=True)
                self.transport.write(req.gen_sip_message)


class Receiver(TwistedBaseClient):

    def connectionMade(self):
        self.factory.call_connected = False
        self.factory.new_call()
        # run receivers one by one
        delay = self.factory.options.interval * self.factory.num
        self.defered_register(delay)

    def dataReceived(self, data):
        super(Receiver, self).dataReceived(data)
        msg = SipMessage.parse(data)[0]
        if msg.is_request and msg.method == "INVITE":
            headers = {}
            for header_name in ["Via", "From", "To", "Call-ID", "CSeq"]:
                headers[header_name] = msg.headers[header_name]
            headers["Content-Length"] = "0"
            method = "INVITE"
            res = SipMessage(status=100, is_request=False, method=method,
                             headers=headers)
            self.factory.log(res, send=True)
            self.transport.write(res.gen_sip_message)
            res = SipMessage(status=180, is_request=False, method=method,
                             headers=headers)
            self.factory.log(res, send=True)
            self.transport.write(res.gen_sip_message)
            headers["Content-Type"] = "application/sdp"
            data = SDP_DATA % self.factory.to_dict
            headers["Content-Length"] = len(data)
            res = SipMessage(status=200, body=data,
                             is_request=False, method=method, headers=headers)
            self.factory.log(res, send=True)
            self.transport.write(res.gen_sip_message)
        elif msg.is_request and msg.method == "BYE":
            headers = {}
            for header_name in ["Via", "From", "To", "Call-ID", "CSeq",
                                "Content-Length"]:
                headers[header_name] = msg.headers[header_name]
                res = SipMessage(status=200, is_request=False, method="BYE",
                                 headers=headers)
            self.factory.log(res, send=True)
            self.transport.write(res.gen_sip_message)
            self.factory.successes += 1
            self.transport.loseConnection()
