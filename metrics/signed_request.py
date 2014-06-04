import hashlib
import base64
import re
import urllib

from M2Crypto import RSA

class BadSignature(Exception):
    pass

def _dequote(str):
    m = re.match(r'^\"((?:\\.|[^\"\\])+)\"$', str)
    if m is not None:
        return re.sub(r'\\(.)', r'\1', m.group(1))
    else:
        return str

# This defines a method of signing an HTTP request using an RSA
# public/private key pair. This is vaguely inspired by OAuth 1.0 signed requests
# but, among other things:
#
#  * We never look inside the body of a POST - even if it is
#    application/x-www-form-urlencoded
#  * We just put the URL whole (double-encoded) into the signature
#  * We don't include the Authorization: header in the signature
#  * We use SHA256 rather than SHA1
#
def check_signature(request, public_key_file):
    if not 'HTTP_X_GNOME_PERF_SIGNATURE' in request.META:
        raise BadSignature("X-GNOME-Perf-Signature header missing")

    sent_signature_header = request.META['HTTP_X_GNOME_PERF_SIGNATURE']
    m = re.match(r'^\s*(\S+)\s+(\S+)\s*$', sent_signature_header)
    if not m:
        raise BadSignature("Can't parse X-GNOME-Perf-Signature")

    signature_method = _dequote(m.group(1))
    try:
        sent_signature = base64.b64decode(m.group(2))
    except TypeError:
        raise BadSignature("Can't decode signature")

    if signature_method != "RSA-SHA256":
        raise BadSignature("Bad signature method '%s'" % signature_method)

    signature_data = request.method + "&"

    if request.is_secure():
        url = "https://"
    else:
        url = "http://"

    url += request.get_host()
    url += request.get_full_path()

    signature_data += urllib.quote(url, "~")
    signature_data += "&&"

    d = hashlib.sha256()
    d.update(signature_data)
    d.update(request.raw_post_data)

    pub = RSA.load_pub_key(public_key_file)
    try:
        pub.verify(d.digest(), sent_signature, 'sha256')
    except RSA.RSAError, e:
        raise BadSignature(e.message)
