import logging
import uuid

from siptest.common.constants import DOMAIN_NAME, AUTH_HEADER_REGEX, URI, \
    AUTH_HEADER, SIP_STATUSES, GET_METHOD_FROM_CSEQ_REGEX
from siptest.common.utils import digest_cal_cha1, digest_calc_response, \
    digest_cal_cha1_2, digest_calc_response_2


class SipMessage:
    """
    Very simple SIP Message
    """
    def __init__(self, method=None, headers={}, body=None,
                 status=None, is_request=True, to=None):
        self.logger = logging.getLogger()
        self.method = method
        self.headers = headers
        self.body = body
        self.status = status
        self.is_request = is_request
        self.logger = logging.getLogger()
        self.to = to

    def copy(self):
        msg = SipMessage(method=self.method, headers=self.headers,
                         body=self.body, status=self.status,
                         is_request=self.is_request, to=self.to)
        return msg

    @property
    def gen_sip_message(self):
        """
        Generate text SIP message
        :return:
        """
        # request
        result = ""
        if self.is_request:
            if self.to:
                result += "%(method)s sip:*%(to)s@%(domain)s SIP/2.0\n" % {
                    'method': self.method,
                    'domain': DOMAIN_NAME,
                    'to': self.to,
                }
            else:
                result += "%(method)s sip:%(domain)s SIP/2.0\n" % {
                    'method': self.method,
                    'domain': DOMAIN_NAME,
                }
        else:
            result += "SIP/2.0 %s %s\n" % (self.status,
                                         SIP_STATUSES[self.status])
        for key, value in self.headers.items():
            result += "%s: %s\n" % (key, value)
        result += "\n"
        if self.body:
            result += self.body
            # result += "\n"
        result = result.encode('utf8')
        return result

    def gen_auth_header(self, server_header, msisdn, password):
        m = AUTH_HEADER_REGEX.match(server_header)
        params = {
            "realm": m.group(3),
            "nonce": m.group(1),
            "opaque": m.group(2),
            "msisdn": msisdn,
            "uri": URI,
            "cnonce": str(uuid.uuid4()).split("-")[0],
            "nonce_count": "00000001",
            "password": password

        }
        digest_responce = digest_cal_cha1_2(
            "md5", params["msisdn"], params["realm"],
            params["password"], params["nonce"], params["cnonce"]
        )
        digest_responce = digest_calc_response_2(
            digest_responce, params["nonce"], params["nonce_count"],
            params["cnonce"], "auth", self.method, params["uri"], None
        )
        params.update({'response': digest_responce})
        client_header = {
          "Proxy-Authorization": AUTH_HEADER % params,
        }
        return client_header

    @classmethod
    def parse(cls, msg):
        """
        Create objects from text message. Can be two or more
        messages in one message text
        :param msg: text message
        :return: List of SipMessage objects
        """
        msg = msg.decode('utf8')
        packages = msg.split("\nSIP/2.0")
        idx = 1
        for p in packages[1:]:
            packages[idx] = "%s%s" % ("SIP/2.0", p)
            idx += 1
        msgs = []
        for p in packages:
            lines = p.split("\n")
            status = None
            is_request = None
            method = None
            if lines[0].startswith("SIP/2.0"):
                is_request = False
                # this is answer
                status = int(lines[0].split()[1])
            elif lines[0].endswith("SIP/2.0\r"):
                is_request = True
                method = lines[0].split()[0]
            lines = lines[1:]
            headers = {}
            lines_count = 0
            for line in lines:
                lines_count += 1
                if not line or line == "\r":
                    break
                l = line.split(":")
                key = l[0]
                l = l[1:]
                value = ":".join(l).strip()
                headers[key] = value
            # get method from CSeq header
            if not is_request:
                if headers.get("CSeq"):
                    m = GET_METHOD_FROM_CSEQ_REGEX.match(headers.get("CSeq"))
                    if m:
                        method = m.group(1)
            # may be there is a body in package
            body = None
            lines = lines[lines_count:]
            if headers.get("Content-Length") and int(headers["Content-Length"]):
                body = []
                for line in lines:
                    if not line or line == "\r":
                        break
                    body.append(line)
                body = "\n".join(body)
            msgs.append(SipMessage(headers=headers, status=status,
                                   is_request=is_request, method=method,
                                   body=body))
        return msgs
