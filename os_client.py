# -*- coding: utf-8 -*-

import options
from oslo_config import cfg

from keystoneauth1 import identity
from keystoneauth1 import session
from neutronclient.v2_0 import client

options.load_db_options()
options.parse_options()
conf = cfg.CONF

OPTS = [
    cfg.StrOpt(
            'auth_url',
            help=_('Authentication endpoint'),
        ),
    cfg.StrOpt(
            'admin_user',
            default='admin',
            help=_('The service admin user name'),
        ),
    cfg.StrOpt(
            'admin_tenant_name',
            default='admin',
            help=_('The service admin tenant name'),
        ),
    cfg.StrOpt(
            'admin_password',
            secret=True,
            default='password',
            help=_('The service admin password'),
        ),
    cfg.StrOpt(
            'admin_user_domain',
            default='admin',
            help=_('The admin user domain name'),
        ),
    cfg.StrOpt(
            'admin_project_domain',
            default='admin',
            help=_('The admin project domain name'),
        ),
    cfg.StrOpt(
            'region',
            default='RegionOne',
            help=_('The deployment region'),
        ),
    cfg.StrOpt(
            'service_name',
            default='lbaas',
            help=_('The name of the service'),
        ),
    cfg.StrOpt(
            'auth_version',
            default='3',
            help=_('The auth version used to authenticate'),
        ),
    cfg.StrOpt(
            'endpoint_type',
            default='public',
            help=_('The endpoint_type to be used')
        ),
    cfg.BoolOpt(
            'insecure',
            default=False,
            help=_('Disable server certificate verification')
        )
]

cfg.CONF.register_opts(OPTS, 'service_auth')

# auth_url = "http://10.145.66.215:35357/v2.0"
# admin_user = "admin"
# admin_tenant_name = "admin"
# admin_password="6a0d50676d754c5e"
# auth_version = 2
# insecure = True

auth = identity.Password(
    auth_url=conf.service_auth.auth_url,
    username=conf.service_auth.admin_user,
    password=conf.service_auth.admin_password,
    project_name=conf.service_auth.admin_tenant_name
)
# auth = identity.Password(
    # auth_url=auth_url,
    # username=admin_user,
    # password=admin_password,
    # project_name=admin_tenant_name
# )
sess = session.Session(auth=auth)
neutron_client = client.Client(session=sess)
