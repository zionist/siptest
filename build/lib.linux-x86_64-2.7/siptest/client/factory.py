import datetime
import logging
import multiprocessing
import uuid
import sys
from twisted.internet import reactor, protocol, task

from siptest.client.client import TwistedBaseClient, Sender, Receiver
from siptest.common.constants import DOMAIN_NAME


class BaseClientFactory(protocol.ReconnectingClientFactory, object):
    """
    Common Factory class. Store all common params which
    should be shared between requests
    """
    protocol = TwistedBaseClient

    def __str__(self):
        return "%s:%s" % (self.name, self.msisdn)

    def __init__(self, msisdn, password, options):
        self.num = 0
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
        self.runs = 0
        self.successes = 0
        self.deaths = 0
        self.last_msg_time = None
        self.exit = multiprocessing.Event()

    def new_call(self):
        self.tag = "%s" % str(uuid.uuid4())
        self.branch = str(uuid.uuid4()).split("-")[0]
        self.call_id = "%s" % str(uuid.uuid4())

    def log(self, sip_message, send):
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

    @property
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
        print("Connection failed - goodbye!")
        if self.runs < self.options.runs:
            self.registration_done = False
            reactor.connectTCP(self.options.host, self.options.port, self)
        else:
            reactor.stop()

    def clientConnectionLost(self, connector, reason):
        if self.runs < self.options.runs:
            self.registration_done = False
            reactor.connectTCP(self.options.host, self.options.port, self)
        else:
            reactor.stop()

    # kills dead connects
    def kill_zombie(self):
        def f():
            stop = datetime.datetime.now()
            if self.last_msg_time:
                if (stop - self.last_msg_time).seconds > \
                                self.options.duration + 15:
                    if self.runs < self.options.runs:
                        self.logger.warn("%s was dead try to restarted" % self)
                        self.registration_done = False
                        reactor.connectTCP(self.options.host, self.options.port, self)
                    else:
                        self.logger.error("%s try to kill" % self)
                        self.doStop()
        reactor.callInThread(f)

    def run(self, num=0):
        self.num = num
        l = task.LoopingCall(self.kill_zombie)
        l.start(5)
        reactor.connectTCP(self.options.host, self.options.port, self)
        reactor.run()


class SenderFactory(BaseClientFactory):
    protocol = Sender

    def __init__(self, *args, **kwargs):
        self.to = kwargs.pop("to")
        self.ack_sent = False
        super(SenderFactory, self).__init__(*args, **kwargs)
        self.name = "Sender"
        self.call_connected = False

    @property
    def to_dict(self):
        d = super(SenderFactory, self).to_dict
        d.update({
            "to": self.to
        })
        return d


class ReceiverFactory(BaseClientFactory):
    protocol = Receiver

    def __init__(self, *args, **kwargs):
        super(ReceiverFactory, self).__init__(*args, **kwargs)
        self.name = "Receiver"

