#!/usr/bin/env python
# -*- encoding: utf-8 -*-

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


from collections import OrderedDict
import logging

from py2neo import Bindable, Resource, Node, Relationship, Subgraph, Path, Finished
from py2neo.compat import integer, xstr, ustr
from py2neo.lang import cypher_escape, TextTable
from py2neo.cypher.error.core import CypherError, TransactionError
from py2neo.primitive import TraversableGraph, Record
from py2neo.util import is_collection, deprecated


__all__ = ["CypherEngine", "Transaction", "Result", "cypher_request"]


log = logging.getLogger("py2neo.cypher")


def first_node(x):
    if hasattr(x, "__nodes__"):
        try:
            return next(x.__nodes__())
        except StopIteration:
            raise ValueError("No such node: %r" % x)
    raise ValueError("No such node: %r" % x)


def last_node(x):
    if hasattr(x, "__nodes__"):
        nodes = list(x.__nodes__())
        if nodes:
            return nodes[-1]
    raise ValueError("No such node: %r" % x)


def presubstitute(statement, parameters):
    more = True
    presub_parameters = []
    while more:
        before, opener, key = statement.partition(u"«")
        if opener:
            key, closer, after = key.partition(u"»")
            try:
                value = parameters[key]
                presub_parameters.append(key)
            except KeyError:
                raise KeyError("Expected a presubstitution parameter named %r" % key)
            if isinstance(value, integer):
                value = ustr(value)
            elif isinstance(value, tuple) and all(map(lambda x: isinstance(x, integer), value)):
                value = u"%d..%d" % (value[0], value[-1])
            elif is_collection(value):
                value = ":".join(map(cypher_escape, value))
            else:
                value = cypher_escape(value)
            statement = before + value + after
        else:
            more = False
    parameters = {k: v for k, v in parameters.items() if k not in presub_parameters}
    return statement, parameters


def cypher_request(statement, parameters, **kwparameters):
    s = ustr(statement)
    p = {}

    def add_parameters(params):
        if params:
            for k, v in dict(params).items():
                if isinstance(v, (Node, Relationship)):
                    v = v._id
                p[k] = v

    if hasattr(statement, "parameters"):
        add_parameters(statement.parameters)
    add_parameters(dict(parameters or {}, **kwparameters))

    s, p = presubstitute(s, p)

    # OrderedDict is used here to avoid statement/parameters ordering bug
    return OrderedDict([
        ("statement", s),
        ("parameters", p),
        ("resultDataContents", ["REST"]),
    ])


class CypherEngine(Bindable):
    """ Service wrapper for all Cypher functionality, providing access
    to transactions as well as single statement execution and streaming.

    This class will usually be instantiated via a :class:`py2neo.Graph`
    object and will be made available through the
    :attr:`py2neo.Graph.cypher` attribute. Therefore, for single
    statement execution, simply use the :func:`execute` method::

        from py2neo import Graph
        graph = Graph()
        results = graph.cypher.execute("MATCH (n:Person) RETURN n")

    """

    error_class = CypherError

    __instances = {}

    def __new__(cls, transaction_uri):
        try:
            inst = cls.__instances[transaction_uri]
        except KeyError:
            inst = super(CypherEngine, cls).__new__(cls)
            inst.bind(transaction_uri)
            cls.__instances[transaction_uri] = inst
        return inst

    def post(self, statement, parameters=None, **kwparameters):
        """ Post a Cypher statement to this resource, optionally with
        parameters.

        :arg statement: A Cypher statement to execute.
        :arg parameters: A dictionary of parameters.
        :arg kwparameters: Extra parameters supplied by keyword.
        """
        tx = Transaction(self)
        result = tx.run(statement, parameters, **kwparameters)
        tx.post(commit=True)
        return result

    def run(self, statement, parameters=None, **kwparameters):
        """ Execute a single Cypher statement, ignoring any return value.

        :arg statement: A Cypher statement to execute.
        :arg parameters: A dictionary of parameters.
        """
        tx = Transaction(self)
        result = tx.run(statement, parameters, **kwparameters)
        tx.commit()
        return result

    def evaluate(self, statement, parameters=None, **kwparameters):
        """ Execute a single Cypher statement and return the value from
        the first column of the first record returned.

        :arg statement: A Cypher statement to execute.
        :arg parameters: A dictionary of parameters.
        :return: Single return value or :const:`None`.
        """
        tx = Transaction(self)
        result = tx.run(statement, parameters, **kwparameters)
        tx.commit()
        return result.value()

    def create(self, g):
        tx = Transaction(self)
        tx.create(g)
        tx.commit()

    def create_unique(self, t):
        tx = Transaction(self)
        tx.create_unique(t)
        tx.commit()

    def delete(self, g):
        tx = Transaction(self)
        tx.delete(g)
        tx.commit()

    def detach(self, g):
        tx = Transaction(self)
        tx.detach(g)
        tx.commit()

    def begin(self):
        """ Begin a new transaction.

        :rtype: :class:`py2neo.cypher.Transaction`
        """
        return Transaction(self)

    @deprecated("CypherEngine.execute(...) is deprecated, "
                "use CypherEngine.run(...) instead")
    def execute(self, statement, parameters=None, **kwparameters):
        """ Execute a single Cypher statement.

        :arg statement: A Cypher statement to execute.
        :arg parameters: A dictionary of parameters.
        :rtype: :class:`py2neo.cypher.Result`
        """
        tx = Transaction(self)
        result = tx.run(statement, parameters, **kwparameters)
        tx.commit()
        return result


class Transaction(object):
    """ A transaction is a transient resource that allows multiple Cypher
    statements to be executed within a single server transaction.
    """

    error_class = TransactionError

    def __init__(self, cypher):
        log.info("begin")
        self.statements = []
        self.results = []
        self.cypher = cypher
        uri = self.cypher.resource.uri.string
        self._begin = Resource(uri)
        self._begin_commit = Resource(uri + "/commit")
        self._execute = None
        self._commit = None
        self._finished = False
        self.graph = self._begin.graph

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.commit()
        else:
            self.rollback()

    def _assert_unfinished(self):
        if self._finished:
            raise Finished(self)

    @property
    def _id(self):
        """ The internal server ID of this transaction, if available.
        """
        if self._execute is None:
            return None
        else:
            return int(self._execute.uri.path.segments[-1])

    def post(self, commit=False, hydrate=False):
        self._assert_unfinished()
        if commit:
            log.info("commit")
            resource = self._commit or self._begin_commit
            self._finished = True
        else:
            log.info("process")
            resource = self._execute or self._begin
        rs = resource.post({"statements": self.statements})
        location = rs.location
        if location:
            self._execute = Resource(location)
        raw = rs.content
        rs.close()
        self.statements = []
        if "commit" in raw:
            self._commit = Resource(raw["commit"])
        for raw_error in raw["errors"]:
            raise self.error_class.hydrate(raw_error)
        for raw_result in raw["results"]:
            result = self.results.pop(0)
            result._hydrate = hydrate
            result._process(raw_result)

    def process(self):
        """ Send all pending statements to the server for execution, leaving
        the transaction open for further statements. Along with
        :meth:`append <.Transaction.append>`, this method can be used to
        batch up a number of individual statements into a single HTTP request::

            from py2neo import Graph

            graph = Graph()
            statement = "MERGE (n:Person {name:{N}}) RETURN n"

            tx = graph.cypher.begin()

            def add_names(*names):
                for name in names:
                    tx.append(statement, {"N": name})
                tx.process()

            add_names("Homer", "Marge", "Bart", "Lisa", "Maggie")
            add_names("Peter", "Lois", "Chris", "Meg", "Stewie")

            tx.commit()

        """
        self.post(hydrate=True)

    def commit(self):
        """ Send all pending statements to the server for execution and commit
        the transaction.
        """
        self.post(commit=True, hydrate=True)

    def rollback(self):
        """ Rollback the current transaction.
        """
        self._assert_unfinished()
        log.info("rollback")
        try:
            if self._execute:
                self._execute.delete()
        finally:
            self._finished = True

    @deprecated("Transaction.append(...) is deprecated, use Transaction.run(...) instead")
    def append(self, statement, parameters=None, **kwparameters):
        return self.run(statement, parameters, **kwparameters)

    def run(self, statement, parameters=None, **kwparameters):
        """ Add a statement to the current queue of statements to be
        executed.

        :arg statement: the statement to append
        :arg parameters: a dictionary of execution parameters
        """
        self._assert_unfinished()
        self.statements.append(cypher_request(statement, parameters, **kwparameters))
        result = Result(self.graph, self, hydrate=True)
        self.results.append(result)
        return result

    def evaluate(self, statement, parameters=None, **kwparameters):
        return self.run(statement, parameters, **kwparameters).value()

    def create(self, g):
        try:
            nodes = list(g.nodes())
            relationships = list(g.relationships())
        except AttributeError:
            raise TypeError("Object %r is not graphy" % g)
        reads = []
        writes = []
        parameters = {}
        returns = {}
        for i, node in enumerate(nodes):
            node_id = "a%d" % i
            param_id = "x%d" % i
            if node.bound:
                reads.append("MATCH (%s) WHERE id(%s)={%s}" % (node_id, node_id, param_id))
                parameters[param_id] = node._id
            else:
                label_string = "".join(":" + cypher_escape(label)
                                       for label in sorted(node.labels()))
                writes.append("CREATE (%s%s {%s})" % (node_id, label_string, param_id))
                parameters[param_id] = dict(node)
                node.set_bind_pending(self)
            returns[node_id] = node
        for i, relationship in enumerate(relationships):
            if not relationship.bound:
                rel_id = "r%d" % i
                start_node_id = "a%d" % nodes.index(relationship.start_node())
                end_node_id = "a%d" % nodes.index(relationship.end_node())
                type_string = cypher_escape(relationship.type())
                param_id = "y%d" % i
                writes.append("CREATE UNIQUE (%s)-[%s:%s]->(%s) SET %s={%s}" %
                              (start_node_id, rel_id, type_string, end_node_id, rel_id, param_id))
                parameters[param_id] = dict(relationship)
                returns[rel_id] = relationship
                relationship.set_bind_pending(self)
        statement = "\n".join(reads + writes + ["RETURN %s LIMIT 1" % ", ".join(returns)])
        result = self.run(statement, parameters)
        result.cache.update(returns)

    def create_unique(self, t):
        if not isinstance(t, TraversableGraph):
            raise ValueError("Object %r is not traversable" % t)
        if not any(node.bound for node in t.nodes()):
            raise ValueError("At least one node must be bound")
        matches = []
        pattern = []
        writes = []
        parameters = {}
        returns = {}
        node = None
        for i, entity in enumerate(t.traverse()):
            if i % 2 == 0:
                # node
                node_id = "a%d" % i
                param_id = "x%d" % i
                if entity.bound:
                    matches.append("MATCH (%s) "
                                   "WHERE id(%s)={%s}" % (node_id, node_id, param_id))
                    pattern.append("(%s)" % node_id)
                    parameters[param_id] = entity._id
                else:
                    label_string = "".join(":" + cypher_escape(label)
                                           for label in sorted(entity.labels()))
                    pattern.append("(%s%s {%s})" % (node_id, label_string, param_id))
                    parameters[param_id] = dict(entity)
                    entity.set_bind_pending(self)
                returns[node_id] = node = entity
            else:
                # relationship
                rel_id = "r%d" % i
                param_id = "x%d" % i
                type_string = cypher_escape(entity.type())
                template = "-[%s:%s]->" if entity.start_node() == node else "<-[%s:%s]-"
                pattern.append(template % (rel_id, type_string))
                writes.append("SET %s={%s}" % (rel_id, param_id))
                parameters[param_id] = dict(entity)
                if not entity.bound:
                    entity.set_bind_pending(self)
                returns[rel_id] = entity
        statement = "\n".join(matches + ["CREATE UNIQUE %s" % "".join(pattern)] + writes +
                              ["RETURN %s LIMIT 1" % ", ".join(returns)])
        result = self.run(statement, parameters)
        result.cache.update(returns)

    def delete(self, g):
        try:
            nodes = list(g.nodes())
            relationships = list(g.relationships())
        except AttributeError:
            raise TypeError("Object %r is not graphy" % g)
        matches = []
        deletes = []
        parameters = {}
        for i, relationship in enumerate(relationships):
            if relationship.bound:
                rel_id = "r%d" % i
                param_id = "y%d" % i
                matches.append("MATCH ()-[%s]->() "
                               "WHERE id(%s)={%s}" % (rel_id, rel_id, param_id))
                deletes.append("DELETE %s" % rel_id)
                parameters[param_id] = relationship._id
                relationship.unbind()
        for i, node in enumerate(nodes):
            if node.bound:
                node_id = "a%d" % i
                param_id = "x%d" % i
                matches.append("MATCH (%s) "
                               "WHERE id(%s)={%s}" % (node_id, node_id, param_id))
                deletes.append("DELETE %s" % node_id)
                parameters[param_id] = node._id
                node.unbind()
        statement = "\n".join(matches + deletes)
        self.run(statement, parameters)

    def detach(self, g):
        try:
            relationships = list(g.relationships())
        except AttributeError:
            raise TypeError("Object %r is not graphy" % g)
        matches = []
        deletes = []
        parameters = {}
        for i, relationship in enumerate(relationships):
            if relationship.bound:
                rel_id = "r%d" % i
                param_id = "y%d" % i
                matches.append("MATCH ()-[%s]->() "
                               "WHERE id(%s)={%s}" % (rel_id, rel_id, param_id))
                deletes.append("DELETE %s" % rel_id)
                parameters[param_id] = relationship._id
                relationship.unbind()
        statement = "\n".join(matches + deletes)
        self.run(statement, parameters)

    def finished(self):
        """ Indicates whether or not this transaction has been completed or is
        still open.

        :return: :py:const:`True` if this transaction has finished,
                 :py:const:`False` otherwise
        """
        return self._finished


class Result(object):
    """ A stream of records returned from the execution of a Cypher statement.
    """

    def __init__(self, graph, transaction=None, hydrate=False):
        assert transaction is None or isinstance(transaction, Transaction)
        self.graph = graph
        self.transaction = transaction
        self._keys = []
        self._records = []
        self._processed = False
        self._hydrate = hydrate     # TODO  hydrate to record or leave raw
        self.cache = {}

    def __repr__(self):
        return "<Result>"

    def __str__(self):
        return xstr(self.__unicode__())

    def __unicode__(self):
        self._ensure_processed()
        out = ""
        if self._keys:
            table = TextTable([None] + self._keys, border=True)
            for i, record in enumerate(self._records):
                table.append([i + 1] + list(record))
            out = repr(table)
        return out

    def __len__(self):
        self._ensure_processed()
        return len(self._records)

    def __getitem__(self, item):
        self._ensure_processed()
        return self._records[item]

    def __iter__(self):
        self._ensure_processed()
        return iter(self._records)

    def _ensure_processed(self):
        if not self._processed:
            self.transaction.process()

    def _process(self, raw):
        self._keys = keys = raw["columns"]
        if self._hydrate:
            hydrate = self.graph.hydrate
            records = []
            for record in raw["data"]:
                values = []
                for i, value in enumerate(record["rest"]):
                    key = keys[i]
                    cached = self.cache.get(key)
                    values.append(hydrate(value, inst=cached))
                records.append(Record(keys, values))
            self._records = records
        else:
            self._records = [values["rest"] for values in raw["data"]]
        self._processed = True

    def keys(self):
        return self._keys

    def value(self, index=0):
        """ A single value from the first record of this result. If no records
        are available, :const:`None` is returned.
        """
        self._ensure_processed()
        try:
            record = self[0]
        except IndexError:
            return None
        else:
            if len(record) > index:
                return record[index]
            else:
                return None

    def to_subgraph(self):
        """ Convert a Result into a Subgraph.
        """
        self._ensure_processed()
        entities = []
        for record in self._records:
            for value in record:
                if isinstance(value, (Node, Relationship, Path)):
                    entities.append(value)
        return Subgraph(*entities)
