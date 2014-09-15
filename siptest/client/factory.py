import logging
import uuid
from twisted.internet import reactor, protocol
from twisted.internet.error import TCPTimedOutError

from siptest.client.client import TwistedBaseClient, Sender, Receiver, \
    RtpClient
from siptest.common.constants import DOMAIN_NAME


class BaseClientFactory(protocol.ReconnectingClientFactory):
    """
    Common Factory class. Store all common params which
    should be shared between requests
    """
    protocol = TwistedBaseClient

    def __str__(self):
        return "%s:%s" % (self.name, self.msisdn)

    def __init__(self, msisdn, password, options, num):
        self.num = num
        # self.interval = options.interval * num
        self.logger = logging.getLogger()
        self.msisdn = msisdn
        self.password = password
        self.options = options
        self.name = "BaseFactory"
        self.tag = "%s" % str(uuid.uuid4())
        self.branch = str(uuid.uuid4()).split("-")[0]
        # sip requests or responses store
        self.messages = {}
        self.call_id = "%s" % str(uuid.uuid4())
        self.registration_done = False
        self.call_connected = False
        self.active_calls = 0
        self.runs = 0
        self.successes = 0
        self.reconnects = 0
        self.invites_count = 0
        self.requests_done = 0
        self.responses_received = 0

    def parse_sdp(self, msg):
        data = msg.body.split("\n")
        host, port = None, None
        for line in data:
            # m=audio 14572 RTP/AVP 0 101
            if line.startswith("o="):
                host = line.split()[-1:][0]
            if line.startswith("m="):
                port = line.split()[1]
        return host, port

    def connect_udp(self, host, port):
        fake_rtp_client = RtpClient(host, int(port), options=self.options)
        return reactor.listenUDP(int(port), fake_rtp_client)


    def new_call(self):
        self.tag = "%s" % str(uuid.uuid4())
        self.branch = str(uuid.uuid4()).split("-")[0]
        self.call_id = "%s" % str(uuid.uuid4())

    def log(self, sip_message, send=False):
        if send:
            if sip_message.is_request:
                self.logger.debug("%s %s ->" % (self, sip_message.method))
            if not sip_message.is_request:
                self.logger.debug("%s %s %s ->" % (self,
                                                   sip_message.status,
                                                   sip_message.method))
        else:
            if sip_message.is_request:
                self.logger.debug("<- %s %s" % (self, sip_message.method))
            if not sip_message.is_request:
                self.logger.debug("<- %s %s %s" % (self,
                                                   sip_message.status,
                                                   sip_message.method))

    def to_dict(self):
        return {
            'msisdn': self.msisdn,
            'tag': self.tag,
            'call_id': self.call_id,
            'branch': self.branch,
            'domain': DOMAIN_NAME,
            'num': self.num,
            }

    def clientConnectionFailed(self, connector, reason):
        self.logger.warning("%s Connection failed. Doing reconnect" % self)
        if isinstance(reason.value, TCPTimedOutError):
            self.reconnects += 1
            self.run()

    def clientConnectionLost(self, connector, reason):
        self.logger.debug("%s Connection lost" % self)

    def run(self):
        self.runs += 1
        self.new_call()
        self.registration_done = False
        self.call_connected = False
        self.connector = reactor.connectTCP(self.options.host,
                                            self.options.port, self,
                                            timeout=400)


class SenderFactory(BaseClientFactory):
    protocol = Sender

    def __init__(self, *args, **kwargs):
        self.to = kwargs.pop("to")
        self.ack_sent = False
        self.name = "Sender"
        self.call_connected = False
        BaseClientFactory.__init__(self, *args, **kwargs)

    def to_dict(self):
        d = BaseClientFactory.to_dict(self)
        d.update({
            "to": self.to
        })
        return d


class ReceiverFactory(BaseClientFactory):
    protocol = Receiver

    def __init__(self, *args, **kwargs):
        BaseClientFactory.__init__(self, *args, **kwargs)
        self.name = "Receiver"

