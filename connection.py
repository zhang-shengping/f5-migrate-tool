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

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session

import eventlet
eventlet.monkey_patch(thread=True)


def get_engine(conf):

    engine_args = {
        "pool_recycle": conf.database.idle_timeout,
        "echo": False,
        "pool_size": conf.database.max_pool_size,
        "pool_timeout": conf.database.pool_timeout
    }

    return create_engine(conf.database.connection, **engine_args)


class Connection(object):

    __instance = None

    def __new__(cls, conf):
        if not isinstance(cls.__instance, cls):
            cls.__instance = super(Connection, cls).__new__(cls)
            cls.__instance.engine = get_engine(conf)
            cls.__instance.base = declarative_base(cls.__instance.engine)
        return cls.__instance


class Session(object):

    def __init__(self, conn):
        self.connection = conn
        self.engine = self.connection.engine
        self.scope_session = scoped_session(sessionmaker(
            bind=self.connection.engine))

    def __enter__(self):
        # print(self.engine.pool.status())
        session = self.scope_session()
        return session

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.scope_session.remove()
