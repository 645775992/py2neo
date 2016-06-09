#!/usr/bin/env python
# -*- encoding: utf-8 -*-

# Copyright 2011-2016, Nigel Small
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


from py2neo.database.cypher import cypher_escape, cypher_repr


class NodeSelection(object):
    """ A set of criteria representing a selection of nodes from a
    graph.
    """

    def __init__(self, graph, labels=frozenset(), conditions=tuple(), limit=None):
        self.graph = graph
        self.labels = frozenset(labels)
        self.conditions = tuple(conditions)
        self._limit = limit

    def __iter__(self):
        for node, in self.graph.run(self.query):
            yield node

    def one(self):
        """ Evaluate the selection and return the first
        :py:class:`.Node` selected or :py:const:`None` if no matching
        nodes are found.

        :return: a single matching :py:class:`.Node` or :py:const:`None`
        """
        return self.graph.evaluate(self.query)

    @property
    def query(self):
        """ The Cypher query used to select the nodes that match the
        criteria for this selection.

        :return: Cypher query string
        """
        clauses = ["MATCH (_%s)" % "".join(":%s" % cypher_escape(label) for label in self.labels)]
        if self.conditions:
            clauses.append("WHERE %s" % " AND ".join(self.conditions))
        clauses.append("RETURN _")
        if self._limit is not None:
            clauses.append("LIMIT %d" % self._limit)
        return " ".join(clauses)

    def where(self, *conditions, **properties):
        """ Create a new selection based on this selection. The
        criteria specified for refining the selection consist of
        conditions and properties. Conditions are individual Cypher
        expressions that would be found in a `WHERE` clause; properties
        are used as exact matches for property values.

        To refer to the current node within a condition expression, use
        the underscore character ``_``. For example::

            selection.where("_.name =~ 'J.*")

        :param conditions: Cypher expressions to add to the selection
                           `WHERE` clause
        :param properties: exact property match keys and values
        :return: refined selection object
        """
        property_conditions = tuple("_.%s = %s" % (cypher_escape(k), cypher_repr(v)) for k, v in properties.items())
        return self.__class__(self.graph, self.labels, self.conditions + conditions + property_conditions, self._limit)

    def limit(self, amount):
        """ Limit the selection by a maximum number of nodes.

        :param amount: maximum number of nodes to select
        :return: refined selection object
        """
        return self.__class__(self.graph, self.labels, self.conditions, amount)


class NodeSelector(object):
    """ A :py:class:`.NodeSelector` can be used to locate nodes within
    a graph that fulfil a specified set of conditions. Typically, a
    single node can be identified passing a specific label and property
    key-value pair. However, any number of labels and any condition
    supported by the Cypher `WHERE` clause is allowed.

    For a simple selection by label and property::

        >>> from py2neo import Graph
        >>> graph = Graph()
        >>> selector = NodeSelector(graph)
        >>> selected = selector.select("Person", name="Keanu Reeves")
        >>> list(selected)
        [(f9726ea:Person {born:1964,name:"Keanu Reeves"})]

    For a more comprehensive selection using Cypher expressions::

        >>> selected = selector.select("Person").where("_.name =~ 'J.*'", "1960 <= _.born < 1970")
        >>> list(selected)
        [(a03f6eb:Person {born:1967,name:"James Marshall"}),
         (e59993d:Person {born:1966,name:"John Cusack"}),
         (c44901e:Person {born:1960,name:"John Goodman"}),
         (b141775:Person {born:1965,name:"John C. Reilly"}),
         (e40244b:Person {born:1967,name:"Julia Roberts"})]

    Note that the underlying query is only evaluated when the selection
    undergoes iteration. This means that a :py:class:`NodeSelection`
    instance may be reused to query the graph data multiple times.
    """

    selection_class = NodeSelection

    def __init__(self, graph):
        self.graph = graph
        self._all = self.selection_class(self.graph)

    def select(self, *labels, **properties):
        """ Describe a basic node selection using labels and property equality.

        :param labels: node labels to match
        :param properties: set of property keys and values to match
        :return: :py:class:`.NodeSelection` instance
        """
        if labels or properties:
            conditions = tuple("_.%s = %s" % (cypher_escape(k), cypher_repr(v)) for k, v in properties.items())
            return self.selection_class(self.graph, frozenset(labels), conditions)
        else:
            return self._all
