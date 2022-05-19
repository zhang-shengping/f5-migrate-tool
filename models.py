# -*- coding: utf-8 -*-
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import connection
import options
from oslo_config import cfg

from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.orm import backref

options.load_db_options()
options.parse_options()
conf = cfg.CONF

con = connection.Connection(conf)
Base = con.base
metadata = Base.metadata


class Loadbalanceragentbindings(Base):
    __tablename__ = "lbaas_loadbalanceragentbindings"
    __table_args__ = {'autoload': True}

    loadbalancer_id = Column(
        String, ForeignKey('lbaas_loadbalancers.id'),
        primary_key=True)
    agent_id = Column(String)


class Loadbalancer(Base):
    __tablename__ = 'lbaas_loadbalancers'
    __table_args__ = {'autoload': True, 'extend_existing': True}

    project_id = Column("project_id")
    provisioning_status = Column("provisioning_status")
    subnet_id = Column("vip_subnet_id")


class Listener(Base):
    __tablename__ = 'lbaas_listeners'
    __table_args__ = {'autoload': True}

    loadbalancer_id = Column("loadbalancer_id")
    provisioning_status = Column("provisioning_status")


class Pool(Base):
    __tablename__ = 'lbaas_pools'
    __table_args__ = {'autoload': True, 'extend_existing': True}

    loadbalancer_id = Column("loadbalancer_id")
    healthmonitor_id = Column(String, ForeignKey('lbaas_healthmonitors.id'))

    # use eagerly load
    members = relationship("Member", lazy='subquery')
    healthmonitor = relationship("Monitor", uselist=False, lazy='subquery')

    provisioning_status = Column("provisioning_status")


class Monitor(Base):
    __tablename__ = 'lbaas_healthmonitors'
    __table_args__ = {'autoload': True}


class Member(Base):
    __tablename__ = 'lbaas_members'
    __table_args__ = {'autoload': True}

    pool_id = Column(String, ForeignKey('lbaas_pools.id'))

    provisioning_status = Column("provisioning_status")


class Network(Base):
    __tablename__ = 'networks'
    __table_args__ = {'autoload': True}

    # subnets = relationship("Subnet", lazy='subquery')

    subnets = relationship("Subnet", backref=backref(
        "network", lazy='subquery', cascade='delete'))

    # segment_id = Column(String(36), ForeignKey('networksegments.id'))

class Networksegment(Base):
    __tablename__ = 'networksegments'
    __table_args__ = {'autoload': True}

    # network_id = Column(String(36),
                        # ForeignKey('networks.id', ondelete="CASCADE"),
                        # nullable=False)

    network = relationship("Network", backref=backref(
        "segments", lazy='subquery', cascade='delete'))


class Subnet(Base):
    __tablename__ = 'subnets'
    __table_args__ = {'autoload': True}

    network_id = Column(String(36), ForeignKey('networks.id'))
    # segment_id = Column(String(36), ForeignKey('networksegments.id'))
