# Copyright 2011-2012 OpenStack LLC.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
import uuid

from oslo_config import cfg
from oslo_policy import policy
import webob.exc

from barbican.api import middleware as mw
from barbican.common import utils
import barbican.context
from barbican import i18n as u
from barbican.openstack.common import jsonutils as json

LOG = utils.getLogger(__name__)

# TODO(jwood) Need to figure out why config is ignored in this module.
context_opts = [
    cfg.BoolOpt('owner_is_project', default=True,
                help=u._('When true, this option sets the owner of an image '
                         'to be the project. Otherwise, the owner of the '
                         ' image will be the authenticated user issuing the '
                         'request.')),
    cfg.StrOpt('admin_role', default='admin',
               help=u._('Role used to identify an authenticated user as '
                        'administrator.')),
    cfg.BoolOpt('allow_anonymous_access', default=False,
                help=u._('Allow unauthenticated users to access the API with '
                         'read-only privileges. This only applies when using '
                         'ContextMiddleware.')),
]


CONF = cfg.CONF
CONF.register_opts(context_opts)


class BaseContextMiddleware(mw.Middleware):
    def process_response(self, resp):
        request_id = resp.request.headers.get('x-openstack-request-id')
        if not request_id:
            request_id = b'req-{0}'.format(str(uuid.uuid4()))

        resp.headers['x-openstack-request-id'] = request_id
        return resp


class ContextMiddleware(BaseContextMiddleware):
    def __init__(self, app):
        self.policy_enforcer = policy.Enforcer(CONF)
        super(ContextMiddleware, self).__init__(app)

    def process_request(self, req):
        """Convert authentication information into a request context

        Generate a barbican.context.RequestContext object from the available
        authentication headers and store on the 'context' attribute
        of the req object.

        :param req: wsgi request object that will be given the context object
        :raises webob.exc.HTTPUnauthorized: when value of the X-Identity-Status
                                            header is not 'Confirmed' and
                                            anonymous access is disallowed
        """
        if req.headers.get('X-Identity-Status') == 'Confirmed':
            req.context = self._get_authenticated_context(req)
            LOG.debug("==== Inserted barbican auth "
                      "request context: %s ====", req.context.to_dict())
        elif CONF.allow_anonymous_access:
            req.context = self._get_anonymous_context()
            LOG.debug("==== Inserted barbican unauth "
                      "request context: %s ====", req.context.to_dict())
        else:
            raise webob.exc.HTTPUnauthorized()

        # Ensure that down wind mw.Middleware/app can see this context.
        req.environ['barbican.context'] = req.context

    def _get_anonymous_context(self):
        kwargs = {
            'user': None,
            'project': None,
            'roles': [],
            'is_admin': False,
            'read_only': True,
            'policy_enforcer': self.policy_enforcer,
        }
        return barbican.context.RequestContext(**kwargs)

    def _get_authenticated_context(self, req):
        # NOTE(bcwaldon): X-Roles is a csv string, but we need to parse
        # it into a list to be useful
        roles_header = req.headers.get('X-Roles', '')
        roles = [r.strip().lower() for r in roles_header.split(',')]

        # NOTE(bcwaldon): This header is deprecated in favor of X-Auth-Token
        # NOTE(mkbhanda): keeping this just-in-case for swift
        deprecated_token = req.headers.get('X-Storage-Token')

        service_catalog = None
        if req.headers.get('X-Service-Catalog') is not None:
            try:
                catalog_header = req.headers.get('X-Service-Catalog')
                service_catalog = json.loads(catalog_header)
            except ValueError:
                msg = u._('Problem processing X-Service-Catalog')
                LOG.exception(msg)
                raise webob.exc.HTTPInternalServerError(msg)

        kwargs = {
            'user': req.headers.get('X-User-Id'),
            'project': req.headers.get('X-Project-Id'),
            'roles': roles,
            'is_admin': CONF.admin_role.strip().lower() in roles,
            'auth_tok': req.headers.get('X-Auth-Token', deprecated_token),
            'owner_is_project': CONF.owner_is_project,
            'service_catalog': service_catalog,
            'policy_enforcer': self.policy_enforcer,
        }

        return barbican.context.RequestContext(**kwargs)


class UnauthenticatedContextMiddleware(BaseContextMiddleware):
    def _get_project_id_from_header(self, req):
        project_id = req.headers.get('X-Project-Id')
        if not project_id:
            accept_header = req.headers.get('Accept')
            if not accept_header:
                req.headers['Accept'] = 'text/plain'
            raise webob.exc.HTTPBadRequest(detail=u._('Missing X-Project-Id'))

        return project_id

    def process_request(self, req):
        """Create a context without an authorized user."""
        project_id = self._get_project_id_from_header(req)

        kwargs = {
            'user': None,
            'project': project_id,
            'roles': [],
            'is_admin': True
        }

        context = barbican.context.RequestContext(**kwargs)
        context.policy_enforcer = None
        req.environ['barbican.context'] = context
