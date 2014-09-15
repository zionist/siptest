import re

DOMAIN_NAME = "svyaznoy.ru"
SIP_HOST = "82.144.65.34"
SIP_PORT = 5060
RUNS_COUNT = 1
# seconds
CALL_DURATION = 8
INTERVAL = 0.1
AUTH_HEADER_REGEX = 'Digest\s+nonce="(.*?)",' \
                    '\s+opaque="(.*?)",\s+algorithm=md5,' \
                    '\s+realm="(.*?)", qop="auth"'
AUTH_HEADER_REGEX = re.compile(AUTH_HEADER_REGEX)
GET_METHOD_FROM_CSEQ_REGEX = '^\d+\s+(\D+)$'
GET_METHOD_FROM_CSEQ_REGEX = re.compile(GET_METHOD_FROM_CSEQ_REGEX)
AUTH_HEADER = 'Digest realm="%(realm)s", nonce="%(nonce)s", ' \
              'opaque="%(opaque)s", username="%(msisdn)s",  ' \
              'uri="%(uri)s", response="%(response)s", ' \
              'cnonce="%(cnonce)s", nc=%(nonce_count)s, qop=auth'
URI = "sip:svyaznoy.ru"
SDP_DATA = """v=0
o=%(msisdn)s %(num)s 3466 IN IP4 10.0.2.15
s=Talk
c=IN IP4 10.0.2.15
b=AS:380
t=0 0
m=audio 7076 RTP/AVP 120 111 110 0 8 101
a=rtpmap:120 SILK/16000
a=rtpmap:111 speex/16000
a=fmtp:111 vbr=on
a=rtpmap:110 speex/8000
a=fmtp:110 vbr=on
a=rtpmap:101 telephone-event/8000
a=fmtp:101 0-15
"""
SIP_STATUSES = {
    100: "Trying",
    180: "Ringing",
    200: "Ok"
}


