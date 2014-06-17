#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2011-2014, Nigel Small
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
import logging

from py2neo.core import Bindable, Resource, ServiceRoot
from py2neo.packages.urimagic import URI
from py2neo.packages.jsonstream import assembled, grouped
from py2neo.error import ClientError
from py2neo.util import is_collection, deprecated


cypher_log = logging.getLogger(__name__ + ".cypher")


class CypherError(Exception):

    def __init__(self, response):
        self._response = response
        Exception.__init__(self, self.message)

    @property
    def message(self):
        return self._response.message

    @property
    def exception(self):
        return self._response.exception

    @property
    def full_name(self):
        return self._response.full_name

    @property
    def stack_trace(self):
        return self._response.stack_trace

    @property
    def cause(self):
        return self._response.cause

    @property
    def request(self):
        return self._response.request

    @property
    def response(self):
        return self._response


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
def execute(graph, query, params=None, row_handler=None,
            metadata_handler=None, error_handler=None):
    query = CypherQuery(graph, query)
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


class Cypher(Bindable):

    __instances = {}

    def __new__(cls, uri):
        try:
            inst = cls.__instances[uri]
        except KeyError:
            inst = super(Cypher, cls).__new__(cls)
            inst.bind(uri)
            cls.__instances[uri] = inst
        return inst

    def post(self, query, params=None):
        if __debug__:
            cypher_log.debug("Query: " + repr(query))
        payload = {"query": query}
        if params:
            if __debug__:
                cypher_log.debug("Params: " + repr(params))
            payload["params"] = params
        try:
            response = self.resource.post(payload)
        except ClientError as e:
            if e.exception:
                # A CustomCypherError is a dynamically created subclass of
                # CypherError with the same name as the underlying server
                # exception
                CustomCypherError = type(str(e.exception), (CypherError,), {})
                raise CustomCypherError(e)
            else:
                raise CypherError(e)
        else:
            return response

    def execute(self, query, params=None):
        return CypherResults(self.graph, self.post(query, params))

    def execute_one(self, query, params=None):
        try:
            return self.execute(query, params).data[0][0]
        except IndexError:
            return None

    def stream(self, query, params=None):
        """ Execute the query and return a result iterator.
        """
        return IterableCypherResults(self.graph, self.post(query, params))


class CypherQuery(object):
    """ A reusable Cypher query. To create a new query object, a graph and the
    query text need to be supplied::

        >>> from py2neo import Graph, CypherQuery
        >>> graph = Graph()
        >>> query = CypherQuery(graph, "CREATE (a) RETURN a")

    """

    def __init__(self, graph, query):
        self.graph = graph
        self.__cypher_resource = self.graph.cypher.resource
        self.query = query

    def __repr__(self):
        return self.query

    @property
    def string(self):
        """ The text of the query.
        """
        return self.query

    def post(self, **params):
        if __debug__:
            cypher_log.debug("Query: " + repr(self.query))
            if params:
                cypher_log.debug("Params: " + repr(params))
        try:
            response = self.__cypher_resource.post({"query": self.query, "params": params})
        except ClientError as e:
            if e.exception:
                # A CustomCypherError is a dynamically created subclass of
                # CypherError with the same name as the underlying server
                # exception
                CustomCypherError = type(str(e.exception), (CypherError,), {})
                raise CustomCypherError(e)
            else:
                raise CypherError(e)
        else:
            return response

    def run(self, **params):
        """ Execute the query and discard any results.

        :param params:
        """
        self.post(**params).close()

    def execute(self, **params):
        """ Execute the query and return the results.

        :param params:
        :return:
        :rtype: :py:class:`CypherResults <py2neo.neo4j.CypherResults>`
        """
        return CypherResults(self.graph, self.post(**params))

    def execute_one(self, **params):
        """ Execute the query and return the first value from the first row.

        :param params:
        :return:
        """
        try:
            return self.execute(**params).data[0][0]
        except IndexError:
            return None

    def stream(self, **params):
        """ Execute the query and return a result iterator.

        :param params:
        :return:
        :rtype: :py:class:`IterableCypherResults <py2neo.neo4j.IterableCypherResults>`
        """
        return IterableCypherResults(self.graph, self.post(**params))


class CypherResults(object):
    """ A static set of results from a Cypher query.
    """

    # TODO: refactor
    @classmethod
    def _hydrated(cls, graph, data):
        """ Takes assembled data...
        """
        producer = RecordProducer(data["columns"])
        return [
            producer.produce(graph.hydrate(row))
            for row in data["data"]
        ]

    def __init__(self, graph, response):
        content = response.content
        self._columns = tuple(content["columns"])
        self._producer = RecordProducer(self._columns)
        self._data = [
            self._producer.produce(graph.hydrate(row))
            for row in content["data"]
        ]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def __len__(self):
        return len(self._data)

    def __getitem__(self, item):
        return self._data[item]

    @property
    def columns(self):
        """ Column names.
        """
        return self._columns

    @property
    def data(self):
        """ List of result records.
        """
        return self._data

    def __iter__(self):
        return iter(self._data)


class IterableCypherResults(object):
    """ An iterable set of results from a Cypher query.

    ::

        query = graph.cypher.query("START n=node(*) RETURN n LIMIT 10")
        for record in query.stream():
            print record[0]

    Each record returned is cast into a :py:class:`namedtuple` with names
    derived from the resulting column names.

    .. note ::
        Results are available as returned from the server and are decoded
        incrementally. This means that there is no need to wait for the
        entire response to be received before processing can occur.
    """

    def __init__(self, graph, response):
        self._graph = graph
        self._response = response
        self._redo_buffer = []
        self._buffered = self._buffered_results()
        self._columns = None
        self._fetch_columns()
        self._producer = RecordProducer(self._columns)

    def _fetch_columns(self):
        redo = []
        section = []
        for key, value in self._buffered:
            if key and key[0] == "columns":
                section.append((key, value))
            else:
                redo.append((key, value))
                if key and key[0] == "data":
                    break
        self._redo_buffer.extend(redo)
        self._columns = tuple(assembled(section)["columns"])

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def _buffered_results(self):
        for result in self._response:
            while self._redo_buffer:
                yield self._redo_buffer.pop(0)
            yield result

    def __iter__(self):
        for key, section in grouped(self._buffered):
            if key[0] == "data":
                for i, row in grouped(section):
                    yield self._producer.produce(self._graph.hydrate(assembled(row)))

    @property
    def columns(self):
        """ Column names.
        """
        return self._columns

    def close(self):
        """ Close results and free resources.
        """
        self._response.close()


class Session(object):
    """ A Session is the base object from which Cypher transactions are
    created and is instantiated using a root service URI. If unspecified, this
    defaults to the `DEFAULT_URI`.

    ::

        >>> from py2neo import cypher
        >>> session = cypher.Session("http://arthur:excalibur@camelot:9999")

    """

    def __init__(self, uri=None):
        self._uri = URI(uri or ServiceRoot.DEFAULT_URI)
        if self._uri.user_info:
            service_root_uri = "{0}://{1}@{2}:{3}/".format(self._uri.scheme, self._uri.user_info, self._uri.host, self._uri.port)
        else:
            service_root_uri = "{0}://{1}:{2}/".format(self._uri.scheme, self._uri.host, self._uri.port)
        self._service_root = ServiceRoot(service_root_uri)
        self._graph = self._service_root.graph
        try:
            self._transaction_uri = self._graph.resource.metadata["transaction"]
        except KeyError:
            raise NotImplementedError("Cypher transactions are not supported "
                                      "by this server version")

    def create_transaction(self):
        """ Create a new transaction object.

        ::

            >>> from py2neo import cypher
            >>> session = cypher.Session()
            >>> tx = session.create_transaction()

        :return: new transaction object
        :rtype: Transaction
        """
        return Transaction(self._transaction_uri)

    def execute(self, statement, parameters=None):
        """ Execute a single statement and return the results.
        """
        tx = self.create_transaction()
        tx.append(statement, parameters)
        results = tx.execute()
        return results[0]


class Transaction(object):
    """ A transaction is a transient resource that allows multiple Cypher
    statements to be executed within a single server transaction.
    """

    def __init__(self, uri):
        self._begin = Resource(uri)
        self._begin_commit = Resource(uri + "/commit")
        self._execute = None
        self._commit = None
        self._statements = []
        self._finished = False

    def _clear(self):
        self._statements = []

    def _assert_unfinished(self):
        if self._finished:
            raise TransactionFinished()

    @property
    def finished(self):
        """ Indicates whether or not this transaction has been completed or is
        still open.

        :return: :py:const:`True` if this transaction has finished,
                 :py:const:`False` otherwise
        """
        return self._finished

    def append(self, statement, parameters=None):
        """ Append a statement to the current queue of statements to be
        executed.

        :param statement: the statement to execute
        :param parameters: a dictionary of execution parameters
        """
        self._assert_unfinished()
        # OrderedDict is used here to avoid statement/parameters ordering bug
        self._statements.append(OrderedDict([
            ("statement", statement),
            ("parameters", dict(parameters or {})),
            ("resultDataContents", ["REST"]),
        ]))

    def _post(self, resource):
        self._assert_unfinished()
        rs = resource.post({"statements": self._statements})
        location = dict(rs.headers).get("location")
        if location:
            self._execute = Resource(location)
        j = rs.content
        rs.close()
        self._clear()
        if "commit" in j:
            self._commit = Resource(j["commit"])
        if "errors" in j:
            errors = j["errors"]
            if len(errors) >= 1:
                error = errors[0]
                raise TransactionError.new(error["code"], error["message"])
        out = []
        for result in j["results"]:
            producer = RecordProducer(result["columns"])
            out.append([
                producer.produce(self._begin.service_root.graph.hydrate(r["rest"]))
                for r in result["data"]
            ])
        return out

    def execute(self):
        """ Send all pending statements to the server for execution, leaving
        the transaction open for further statements.

        :return: list of results from pending statements
        """
        return self._post(self._execute or self._begin)

    def commit(self):
        """ Send all pending statements to the server for execution and commit
        the transaction.

        :return: list of results from pending statements
        """
        try:
            return self._post(self._commit or self._begin_commit)
        finally:
            self._finished = True

    def rollback(self):
        """ Rollback the current transaction.
        """
        self._assert_unfinished()
        try:
            if self._execute:
                self._execute.delete()
        finally:
            self._finished = True


class TransactionError(Exception):
    """ Raised when an error occurs while processing a Cypher transaction.
    """

    @classmethod
    def new(cls, code, message):
        CustomError = type(str(code), (cls,), {})
        return CustomError(message)

    def __init__(self, message):
        Exception.__init__(self, message)


class TransactionFinished(Exception):
    """ Raised when actions are attempted against a finished Transaction.
    """

    def __init__(self):
        pass

    def __repr__(self):
        return "Transaction finished"


class Record(object):
    """ A single row of a Cypher execution result, holding a sequence of named
    values.
    """

    def __init__(self, producer, values):
        self._producer = producer
        self._values = tuple(values)

    def __repr__(self):
        return "Record(columns={0}, values={1})".format(self._producer.columns, self._values)

    def __getattr__(self, attr):
        return self._values[self._producer.column_indexes[attr]]

    def __getitem__(self, item):
        if isinstance(item, (int, slice)):
            return self._values[item]
        else:
            return self._values[self._producer.column_indexes[item]]

    def __len__(self):
        return len(self._producer.columns)

    @property
    def columns(self):
        """ The column names defined for this record.

        :return: tuple of column names
        """
        return self._producer.columns

    @property
    def values(self):
        """ The values stored in this record.

        :return: tuple of values
        """
        return self._values


class RecordProducer(object):

    def __init__(self, columns):
        self._columns = tuple(columns)
        self._column_indexes = dict((b, a) for a, b in enumerate(columns))

    def __repr__(self):
        return "RecordProducer(columns={0})".format(self._columns)

    @property
    def columns(self):
        return self._columns

    @property
    def column_indexes(self):
        return self._column_indexes

    def produce(self, values):
        """ Produce a record from a set of values.
        """
        return Record(self, values)


# TODO keep in __init__ as wrapper
# TODO: add support for Node, NodePointer, Path, Rel, Relationship and Rev
def dumps(obj, separators=(", ", ": "), ensure_ascii=True):
    """ Dumps an object as a Cypher expression string.

    :param obj:
    :param separators:
    :return:
    """

    def dump_mapping(obj):
        buffer = ["{"]
        link = ""
        for key, value in obj.items():
            buffer.append(link)
            if " " in key:
                buffer.append("`")
                buffer.append(key.replace("`", "``"))
                buffer.append("`")
            else:
                buffer.append(key)
            buffer.append(separators[1])
            buffer.append(dumps(value, separators=separators,
                                ensure_ascii=ensure_ascii))
            link = separators[0]
        buffer.append("}")
        return "".join(buffer)

    def dump_collection(obj):
        buffer = ["["]
        link = ""
        for value in obj:
            buffer.append(link)
            buffer.append(dumps(value, separators=separators,
                                ensure_ascii=ensure_ascii))
            link = separators[0]
        buffer.append("]")
        return "".join(buffer)

    if isinstance(obj, dict):
        return dump_mapping(obj)
    elif is_collection(obj):
        return dump_collection(obj)
    else:
        return json.dumps(obj, ensure_ascii=ensure_ascii)
