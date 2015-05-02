# Copyright (c) 2015 Cisco Systems
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
The following functions were created for testing purposes.
"""
from OpenSSL import crypto


def create_key_pair(type, bits):
    key_pair = crypto.PKey()
    key_pair.generate_key(type, bits)
    return key_pair


def get_valid_csr_object():
    """Create a valid X509Req object"""
    key_pair = create_key_pair(crypto.TYPE_RSA, 2048)
    csr = crypto.X509Req()
    subject = csr.get_subject()
    setattr(subject, "CN", "host.example.net")
    csr.set_pubkey(key_pair)
    csr.sign(key_pair, "sha256")
    return csr


def create_good_csr():
    """Generate a CSR that will pass validation."""
    csr = get_valid_csr_object()
    pem = crypto.dump_certificate_request(crypto.FILETYPE_PEM, csr)
    return pem


def create_csr_that_has_not_been_signed():
    """Generate a CSR that has not been signed."""
    key_pair = create_key_pair(crypto.TYPE_RSA, 2048)
    csr = crypto.X509Req()
    subject = csr.get_subject()
    setattr(subject, "CN", "host.example.net")
    csr.set_pubkey(key_pair)
    pem = crypto.dump_certificate_request(crypto.FILETYPE_PEM, csr)
    return pem


def create_csr_signed_with_wrong_key():
    """Generate a CSR that has been signed by the wrong key."""
    key_pair1 = create_key_pair(crypto.TYPE_RSA, 2048)
    key_pair2 = create_key_pair(crypto.TYPE_RSA, 2048)
    csr = crypto.X509Req()
    subject = csr.get_subject()
    setattr(subject, "CN", "host.example.net")
    # set public key from key pair 1
    csr.set_pubkey(key_pair1)
    # sign with public key from key pair 2
    csr.sign(key_pair2, "sha256")
    pem = crypto.dump_certificate_request(crypto.FILETYPE_PEM, csr)
    return pem


def create_bad_csr():
    """Generate a CSR that will not parse."""
    return "Bad PKCS10 Data"


def create_csr_with_bad_subject_dn():
    """Generate a CSR that has a bad subject dn."""
    key_pair = create_key_pair(crypto.TYPE_RSA, 2048)
    csr = crypto.X509Req()
    subject = csr.get_subject()
    # server certs require attribute 'CN'
    setattr(subject, "UID", "bar")
    csr.set_pubkey(key_pair)
    csr.sign(key_pair, "sha256")
    pem = crypto.dump_certificate_request(crypto.FILETYPE_PEM, csr)
    return pem
