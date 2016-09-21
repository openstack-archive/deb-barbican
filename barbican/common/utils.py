# Copyright (c) 2013-2014 Rackspace, Inc.
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
Common utilities for Barbican.
"""
import collections
import importlib
import mimetypes
import uuid

from oslo_log import log
import pecan
import six
from six.moves.urllib import parse

from barbican.common import config
from barbican import i18n as u


CONF = config.CONF


# Current API version
API_VERSION = 'v1'

# Added here to remove cyclic dependency.
# In barbican.model.models module SecretType.OPAQUE was imported from
# barbican.plugin.interface.secret_store which introduces a cyclic dependency
# if `secret_store` plugin needs to use db model classes. So moving shared
# value to another common python module which is already imported in both.
SECRET_TYPE_OPAQUE = "opaque"


def _do_allow_certain_content_types(func, content_types_list=[]):
    # Allows you to bypass pecan's content-type restrictions
    cfg = pecan.util._cfg(func)
    cfg.setdefault('content_types', {})
    cfg['content_types'].update((value, '')
                                for value in content_types_list)
    return func


def allow_certain_content_types(*content_types_list):
    def _wrapper(func):
        return _do_allow_certain_content_types(func, content_types_list)
    return _wrapper


def allow_all_content_types(f):
    return _do_allow_certain_content_types(f, mimetypes.types_map.values())


def get_base_url_from_request():
    """Derive base url from wsgi request if CONF.host_href is not set

    Use host.href as base URL if its set in barbican.conf.
    If its not set, then derives value from wsgi request. WSGI request uses
    HOST header or HTTP_X_FORWARDED_FOR header (in case of proxy) for host +
    port part of its url. Proxies can also set HTTP_X_FORWARDED_PROTO header
    for indicating http vs https.

    Some of unit tests does not have pecan context that's why using request
    attr check on pecan instance.
    """
    if not CONF.host_href and hasattr(pecan.request, 'url'):
        p_url = parse.urlsplit(pecan.request.url)
        base_url = '%s://%s' % (p_url.scheme, p_url.netloc)
        return base_url
    else:  # when host_href is set or flow is not within wsgi request context
        return CONF.host_href


def hostname_for_refs(resource=None):
    """Return the HATEOAS-style return URI reference for this service."""
    base_url = get_base_url_from_request()
    ref = ['{base}/{version}'.format(base=base_url, version=API_VERSION)]
    if resource:
        ref.append('/' + resource)
    return ''.join(ref)


# Return a logger instance.
#   Note: Centralize access to the logger to avoid the dreaded
#   'ArgsAlreadyParsedError: arguments already parsed: cannot
#   register CLI option'
#   error.
def getLogger(name):
    return log.getLogger(name)


def get_accepted_encodings(req):
    """Returns a list of client acceptable encodings sorted by q value.

    For details see: http://tools.ietf.org/html/rfc2616#section-14.3

    :param req: request object
    :returns: list of client acceptable encodings sorted by q value.
    """
    header = req.get_header('Accept-Encoding')

    return get_accepted_encodings_direct(header)


def get_accepted_encodings_direct(content_encoding_header):
    """Returns a list of client acceptable encodings sorted by q value.

    For details see: http://tools.ietf.org/html/rfc2616#section-14.3

    :param req: request object
    :returns: list of client acceptable encodings sorted by q value.
    """
    if content_encoding_header is None:
        return None

    Encoding = collections.namedtuple('Encoding', ['coding', 'quality'])

    encodings = list()
    for enc in content_encoding_header.split(','):
        if ';' in enc:
            coding, qvalue = enc.split(';')
            try:
                qvalue = qvalue.split('=')[1]
                quality = float(qvalue.strip())
            except ValueError:
                # can't convert quality to float
                return None
            if quality > 1.0 or quality < 0.0:
                # quality is outside valid range
                return None
            if quality > 0.0:
                encodings.append(Encoding(coding.strip(), quality))
        else:
            encodings.append(Encoding(enc.strip(), 1))

    # Sort the encodings by quality
    encodings = sorted(encodings, key=lambda e: e.quality, reverse=True)

    return [encoding.coding for encoding in encodings]


def generate_fullname_for(instance):
    """Produce a fully qualified class name for the specified instance.

    :param instance: The instance to generate information from.
    :return: A string providing the package.module information for the
    instance.
    :raises: ValueError if the given instance is null
    """
    if not instance:
        raise ValueError(u._("Cannot generate a fullname for a null instance"))

    module = type(instance).__module__
    class_name = type(instance).__name__

    if module is None or module == six.moves.builtins.__name__:
        return class_name
    return "{module}.{class_name}".format(module=module, class_name=class_name)


def get_class_for(module_name, class_name):
    """Create a Python class from its text-specified components."""
    # Load the module via name, raising ImportError if module cannot be
    # loaded.
    python_module = importlib.import_module(module_name)

    # Load and return the resolved Python class, raising AttributeError if
    # class cannot be found.
    return getattr(python_module, class_name)


def generate_uuid():
    return str(uuid.uuid4())


def is_multiple_backends_enabled():
    secretstore_conf = config.get_module_config('secretstore')
    return secretstore_conf.secretstore.enable_multiple_secret_stores
