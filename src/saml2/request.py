import logging

from attribute_converter import to_local
from saml2 import time_util
from saml2 import s_utils
from saml2.s_utils import OtherError

from saml2.validate import valid_instance
from saml2.validate import NotValid
from saml2.response import IncorrectlySigned

logger = logging.getLogger(__name__)

def _dummy(_arg):
    return None
    
class Request(object):
    def __init__(self, sec_context, receiver_addrs, timeslack=0):
        self.sec = sec_context
        self.receiver_addrs = receiver_addrs
        self.timeslack = timeslack
        self.xmlstr = ""
        self.name_id = ""
        self.message = None
        self.not_on_or_after = 0

        self.signature_check = _dummy # has to be set !!!
    
    def _clear(self):
        self.xmlstr = ""
        self.name_id = ""
        self.message = None
        self.not_on_or_after = 0

    def _loads(self, xmldata, decode=True):
        if decode:
            logger.debug("Expected to decode and inflate xml data")
            decoded_xml = s_utils.decode_base64_and_inflate(xmldata)
        else:
            decoded_xml = xmldata
    
        # own copy
        self.xmlstr = decoded_xml[:]
        logger.info("xmlstr: %s" % (self.xmlstr,))
        try:
            self.message = self.signature_check(decoded_xml)
        except TypeError:
            raise
        except Exception, excp:
            logger.info("EXCEPTION: %s", excp)
    
        if not self.message:
            logger.error("Response was not correctly signed")
            logger.info(decoded_xml)
            raise IncorrectlySigned()

        logger.info("request: %s" % (self.message,))

        try:
            valid_instance(self.message)
        except NotValid, exc:
            logger.error("Not valid request: %s" % exc.args[0])
            raise
        
        return self
    
    def issue_instant_ok(self):
        """ Check that the request was issued at a reasonable time """
        upper = time_util.shift_time(time_util.time_in_a_while(days=1),
                                    self.timeslack).timetuple()
        lower = time_util.shift_time(time_util.time_a_while_ago(days=1),
                                    -self.timeslack).timetuple()
        # print "issue_instant: %s" % self.message.issue_instant
        # print "%s < x < %s" % (lower, upper)
        issued_at = time_util.str_to_time(self.message.issue_instant)
        return issued_at > lower and issued_at < upper

    def _verify(self):            
        assert self.message.version == "2.0"
        if self.message.destination and \
            self.message.destination not in self.receiver_addrs:
            logger.error("%s != %s" % (self.message.destination,
                                                self.receiver_addrs))
            raise OtherError("Not destined for me!")
            
        assert self.issue_instant_ok()
        return self

    def loads(self, xmldata, decode=True):
        return self._loads(xmldata, decode)

    def verify(self):
        try:
            return self._verify()
        except AssertionError:
            return None
            
    def subject_id(self):
        """ The name of the subject can be in either of 
        BaseID, NameID or EncryptedID

        :return: The identifier if there is one
        """

        if "subject" in self.message.keys():
            _subj = self.message.subject
            if "base_id" in _subj.keys() and _subj.base_id:
                return _subj.base_id
            elif _subj.name_id:
                return _subj.name_id
        else:
            if "base_id" in self.message.keys() and self.message.base_id:
                return self.message.base_id
            elif self.message.name_id:
                return self.message.name_id
            else: # EncryptedID
                pass
            
    def sender(self):
        return self.message.issuer.text()
        
class LogoutRequest(Request):
    def __init__(self, sec_context, receiver_addrs, timeslack=0):
        Request.__init__(self, sec_context, receiver_addrs, timeslack)
        self.signature_check = self.sec.correctly_signed_logout_request
        
            
class AttributeQuery(Request):
    def __init__(self, sec_context, receiver_addrs, timeslack=0):
        Request.__init__(self, sec_context, receiver_addrs, timeslack)
        self.signature_check = self.sec.correctly_signed_attribute_query
    
    def attribute(self):
        """ Which attributes that are sought for """
        return []

class AuthnRequest(Request):
    def __init__(self, sec_context, attribute_converters, receiver_addrs,
                 timeslack=0):
        Request.__init__(self, sec_context, receiver_addrs, timeslack)
        self.attribute_converters = attribute_converters
        self.signature_check = self.sec.correctly_signed_authn_request


    def attributes(self):
        return to_local(self.attribute_converters, self.message)
            

class AuthzRequest(Request):
    def __init__(self, sec_context, receiver_addrs, timeslack=0):
        Request.__init__(self, sec_context, receiver_addrs, timeslack)
        self.signature_check = self.sec.correctly_signed_logout_request

    def action(self):
        """ Which action authorization is requested for """
        pass

    def evidence(self):
        """ The evidence on which the decision is based """
        pass

    def resource(self):
        """ On which resource the action is expected to occur """
        pass