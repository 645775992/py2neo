#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2011-2013, Nigel Small
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

""" Cypher Query Language module.
"""


from __future__ import unicode_literals

from collections import OrderedDict
import json

from .neo4j import DEFAULT_URI, CypherQuery, CypherError, ServiceRoot, Resource, _hydrated
from .util import deprecated, Record
from .packages.httpstream import URI


@deprecated("The cypher module is deprecated, use "
            "neo4j.CypherQuery instead")
class Metadata(object):
    """Metadata for query results.
    """

    #: List of column names
    columns = []

    def __init__(self, columns=None):
        self.columns = columns or []


@deprecated("The cypher module is deprecated, use "
            "neo4j.CypherQuery instead")
def execute(graph_db, query, params=None, row_handler=None,
            metadata_handler=None, error_handler=None):
    query = CypherQuery(graph_db, query)
    data, metadata = [], None
    try:
        results = query.execute(**params or {})
    except CypherError as err:
        if error_handler:
            error_handler(err.message, err.exception, err.stack_trace)
        else:
            raise
    else:
        metadata = Metadata(results.columns)
        if metadata_handler:
            metadata_handler(metadata)
        if row_handler:
            for record in results:
                row_handler(list(record))
            return data, metadata
        else:
            return [list(record) for record in results], metadata


def dumps(obj, separators=(", ", ": "), ensure_ascii=True):
    """ Dumps an object as a Cypher expression string.

    :param obj:
    :param separators:
    :return:
    """
    if isinstance(obj, dict):
        buffer = ["{"]
        link = ""
        for key, value in obj.items():
            buffer.append(link)
            if " " in key:
                buffer.append("`")
                buffer.append(key)
                buffer.append("`")
            else:
                buffer.append(key)
            buffer.append(separators[1])
            buffer.append(dumps(value, separators=separators,
                                ensure_ascii=ensure_ascii))
            link = separators[0]
        buffer.append("}")
        return "".join(buffer)
    elif isinstance(obj, (tuple, set, list)):
        buffer = ["["]
        link = ""
        for value in obj:
            buffer.append(link)
            buffer.append(dumps(value, separators=separators,
                                ensure_ascii=ensure_ascii))
            link = separators[0]
        buffer.append("]")
        return "".join(buffer)
    else:
        return json.dumps(obj, ensure_ascii=ensure_ascii)
        
        
class Session(object):

    def __init__(self, uri=None):
        self._uri = URI(uri or DEFAULT_URI)
        if self._uri.user_info:
            service_root_uri = "{0}://{1}@{2}:{3}/".format(self._uri.scheme, self._uri.user_info, self._uri.host, self._uri.port)
        else:
            service_root_uri = "{0}://{1}:{2}/".format(self._uri.scheme, self._uri.host, self._uri.port)
        self._service_root = ServiceRoot.get_instance(service_root_uri)
        self._graph_db = self._service_root.graph_db
        try:
            self._transaction_uri = self._graph_db.__metadata__["transaction"]
        except KeyError:
            raise NotImplementedError("Cypher transactions are not supported "
                                      "by this server version")
        
    def create_transaction(self):
        return Transaction(self._transaction_uri)

        
class Transaction(object):

    def __init__(self, uri):
        self._begin = Resource(uri)
        self._begin_commit = Resource(uri + "/commit")
        self._execute = None
        self._commit = None
        self.clear()

    def clear(self):
        self._statements = []
    
    def append(self, statement, parameters=None):
        # OrderedDict is used here to avoid statement/parameters ordering bug
        self._statements.append(OrderedDict([
            ("statement", statement),
            ("parameters", dict(parameters or {})),
            ("resultDataContents", ["REST"]),
        ]))

    def _post(self, resource):
        rs = resource._post({"statements": self._statements})
        location = dict(rs.headers).get("Location")
        if location:
            self._execute = Resource(location)
        j = rs.json
        rs.close()
        self.clear()
        if "commit" in j:
            self._commit = Resource(j["commit"])
        if "errors" in j:
            errors = j["errors"]
            if len(errors) >= 1:
                error = errors[0]
                raise TransactionError(error["code"], error["status"], error["message"])
        return [
            [
                Record(result["columns"], _hydrated(r["rest"]))
                for r in result["data"]
            ]
            for result in j["results"]
        ]
        
    def execute(self):
        return self._post(self._execute or self._begin)

    def commit(self):
        return self._post(self._commit or self._begin_commit)


class TransactionError(Exception):

    def __init__(self, code, status, message):
        self.code = code
        self.status = status
        self.message = message

    def __repr__(self):
        return self.message

    def __str__(self):
        return self.message

