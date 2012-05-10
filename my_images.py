import my_api as api

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User
from django.http import *
from django.utils.text import normalize_newlines

import logging
from openstackx.api import exceptions as api_exceptions

LOG = logging.getLogger('my_test')


def mylogin(request, data):

    def is_admin(token):
        for role in token.user['roles']:
            if role['name'].lower() == 'admin':
                return True
        return False

    try:
        if data.get('tenant'):
            token = api.token_create(request,
                                     data.get('tenant'),
                                     data['username'],
                                     data['password'])

            tenants = api.tenant_list_for_token(request, token.id)
            tenant = None
            for t in tenants:
                if t.id == data.get('tenant'):
                    tenant = t
        else:
            # We are logging in without tenant
            token = api.token_create(request,
                                     '',
                                     data['username'],
                                     data['password'])

            # Unscoped token
            request.session['unscoped_token'] = token.id

            def get_first_tenant_for_user():
                tenants = api.tenant_list_for_token(request, token.id)
                return tenants[0] if len(tenants) else None

            # Get the tenant list, and log in using first tenant
            # FIXME (anthony): add tenant chooser here?
            tenant = get_first_tenant_for_user()

            # Abort if there are no valid tenants for this user
            if not tenant:
                messages.error(request, 'No tenants present for user: %s' %
                                        data['username'])
                return

            # Create a token
            token = api.token_create_scoped_with_token(request,
                                    data.get('tenant', tenant.id),
                                    token.id)

        request.session['admin'] = is_admin(token)
        request.session['serviceCatalog'] = token.serviceCatalog

        #LOG.info('Login form for user "%s". Service Catalog data:\n%s' %
        #         (data['username'], token.serviceCatalog))

        request.session['tenant'] = tenant.name
        request.session['tenant_id'] = tenant.id
        request.session['token'] = token.id
        request.session['user'] = data['username']

        #return shortcuts.redirect('dash_overview')

    except api_exceptions.Unauthorized as e:
        msg = 'Error authenticating: %s' % e.message
        LOG.exception(msg)
        messages.error(request, msg)
    except api_exceptions.ApiException as e:
        messages.error(request, 'Error authenticating with keystone: %s' %
                                 e.message)

def mycreate(request, data):
    try:
        name = data['name']
        image_id = data['image_id']
        flavor_id = data['flavor_id']
        key_name = data.get('key_name')
        user_data = normalize_newlines(data.get('user_data'))
        security_groups = data.get('security_groups')

        image = api.image_get(request, image_id)
        flavor = api.flavor_get(request, flavor_id)

        api.server_create(request,
                          name,
                          image,
                          flavor,
                          key_name,
                          user_data,
                          security_groups)

        LOG.info('Instance was successfully launched')
        messages.success(request, msg)

    except api_exceptions.ApiException, e:
        LOG.exception('ApiException while creating instances of image "%s"'
                       % image_id)
        messages.error(request,
                       'Unable to launch instance: %s' % e.message)

request = HttpRequest()
request.path = '/auth/login'
request.method = 'POST'
request.session = {}
user = User()
request.user = user

login_data = {'username': 'admin',
        'password': 'letmein',}

mylogin(request, login_data)

create_data = {'name': 'testVM',
        'image_id': '1',
        'flavor_id': '2',
        'key_name': '',
        'user_data': '',
        'security_groups': ''}

mycreate(request, create_data)
