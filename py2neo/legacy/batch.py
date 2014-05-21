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


from __future__ import division, unicode_literals

from py2neo.packages.urimagic import percent_encode

from py2neo.neo4j import Node, Relationship,  \
    _cast, _rel, ReadBatch as _ReadBatch, WriteBatch as _WriteBatch
from py2neo.util import *


__all__ = ["LegacyReadBatch", "LegacyWriteBatch"]


class LegacyReadBatch(_ReadBatch):
    """ Generic batch execution facility for data read requests,
    """

    def get_indexed_nodes(self, index, key, value):
        """ Fetch all nodes indexed under a given key-value pair.

        :param index: index name or instance
        :type index: :py:class:`str` or :py:class:`Index`
        :param key: key under which nodes are indexed
        :type key: :py:class:`str`
        :param value: value under which nodes are indexed
        :return: batch request object
        """
        index = self._index(Node, index)
        uri = index._searcher_stem_for_key(key) + percent_encode(value)
        return self.append_get(uri)


class LegacyWriteBatch(_WriteBatch):
    """ Generic batch execution facility for data write requests. Most methods
    return a :py:class:`BatchRequest <py2neo.neo4j.BatchRequest>` object that
    can be used as a reference in other methods. See the
    :py:meth:`create <py2neo.neo4j.WriteBatch.create>` method for an example
    of this.
    """

    def __init__(self, graph):
        super(LegacyWriteBatch, self).__init__(graph)
        self.__new_uniqueness_modes = None

    @property
    def supports_index_uniqueness_modes(self):
        return self._graph.supports_index_uniqueness_modes

    def _assert_can_create_or_fail(self):
        if not self.supports_index_uniqueness_modes:
            raise NotImplementedError("Uniqueness mode `create_or_fail` "
                                      "requires version 1.9 or above")

    ### ADD TO INDEX ###

    def _add_to_index(self, cls, index, key, value, entity, query=None):
        uri = self._uri_for(self._index(cls, index), query=query)
        return self.append_post(uri, {
            "key": key,
            "value": value,
            "uri": self._uri_for(entity),
        })

    def add_to_index(self, cls, index, key, value, entity):
        """ Add an existing node or relationship to an index.

        :param cls: the type of indexed entity
        :type cls: :py:class:`Node <py2neo.neo4j.Node>` or
                   :py:class:`Relationship <py2neo.neo4j.Relationship>`
        :param index: index or index name
        :type index: :py:class:`Index <py2neo.neo4j.Index>` or :py:class:`str`
        :param key: index entry key
        :type key: :py:class:`str`
        :param value: index entry value
        :param entity: node or relationship to add to the index
        :type entity: concrete or reference
        :return: batch request object
        """
        return self._add_to_index(cls, index, key, value, entity)

    def add_to_index_or_fail(self, cls, index, key, value, entity):
        """ Add an existing node or relationship uniquely to an index, failing
        the entire batch if such an entry already exists.

        .. warning::
            Uniqueness modes for legacy indexes have been broken in recent
            server versions and therefore this method may not work as expected.

        :param cls: the type of indexed entity
        :type cls: :py:class:`Node <py2neo.neo4j.Node>` or
                   :py:class:`Relationship <py2neo.neo4j.Relationship>`
        :param index: index or index name
        :type index: :py:class:`Index <py2neo.neo4j.Index>` or :py:class:`str`
        :param key: index entry key
        :type key: :py:class:`str`
        :param value: index entry value
        :param entity: node or relationship to add to the index
        :type entity: concrete or reference
        :return: batch request object
        """
        self._assert_can_create_or_fail()
        query = "uniqueness=create_or_fail"
        return self._add_to_index(cls, index, key, value, entity, query)

    def get_or_add_to_index(self, cls, index, key, value, entity):
        """ Fetch a uniquely indexed node or relationship if one exists,
        otherwise add an existing entity to the index.

        :param cls: the type of indexed entity
        :type cls: :py:class:`Node <py2neo.neo4j.Node>` or
                   :py:class:`Relationship <py2neo.neo4j.Relationship>`
        :param index: index or index name
        :type index: :py:class:`Index <py2neo.neo4j.Index>` or :py:class:`str`
        :param key: index entry key
        :type key: :py:class:`str`
        :param value: index entry value
        :param entity: node or relationship to add to the index
        :type entity: concrete or reference
        :return: batch request object
        """
        if self.supports_index_uniqueness_modes:
            query = "uniqueness=get_or_create"
        else:
            query = "unique"
        return self._add_to_index(cls, index, key, value, entity, query)

    ### CREATE IN INDEX ###

    def _create_in_index(self, cls, index, key, value, abstract, query=None):
        uri = self._uri_for(self._index(cls, index), query=query)
        abstract = _cast(abstract, cls=cls, abstract=True)
        if cls is Node:
            return self.append_post(uri, {
                "key": key,
                "value": value,
                "properties": abstract.properties,
            })
        elif cls is Relationship:
            return self.append_post(uri, {
                "key": key,
                "value": value,
                "start": self._uri_for(abstract._start_node),
                "type": str(abstract._type),
                "end": self._uri_for(abstract._end_node),
                "properties": abstract._properties or {},
            })
        else:
            raise TypeError(cls)

    # Removed create_in_index as parameter combination not supported by server

    def create_in_index_or_fail(self, cls, index, key, value, abstract=None):
        """ Create a new node or relationship and add it uniquely to an index,
        failing the entire batch if such an entry already exists.

        .. warning::
            Uniqueness modes for legacy indexes have been broken in recent
            server versions and therefore this method may not work as expected.

        :param cls: the type of indexed entity
        :type cls: :py:class:`Node <py2neo.neo4j.Node>` or
                   :py:class:`Relationship <py2neo.neo4j.Relationship>`
        :param index: index or index name
        :type index: :py:class:`Index <py2neo.neo4j.Index>` or :py:class:`str`
        :param key: index entry key
        :type key: :py:class:`str`
        :param value: index entry value
        :param abstract: abstract node or relationship to create
        :return: batch request object
        """
        self._assert_can_create_or_fail()
        query = "uniqueness=create_or_fail"
        return self._create_in_index(cls, index, key, value, abstract, query)

    def get_or_create_in_index(self, cls, index, key, value, abstract=None):
        """ Fetch a uniquely indexed node or relationship if one exists,
        otherwise create a new entity and add that to the index.

        :param cls: the type of indexed entity
        :type cls: :py:class:`Node <py2neo.neo4j.Node>` or
                   :py:class:`Relationship <py2neo.neo4j.Relationship>`
        :param index: index or index name
        :type index: :py:class:`Index <py2neo.neo4j.Index>` or :py:class:`str`
        :param key: index entry key
        :type key: :py:class:`str`
        :param value: index entry value
        :param abstract: abstract node or relationship to create
        :return: batch request object
        """
        if self.supports_index_uniqueness_modes:
            query = "uniqueness=get_or_create"
        else:
            query = "unique"
        return self._create_in_index(cls, index, key, value, abstract, query)

    ### REMOVE FROM INDEX ###

    def remove_from_index(self, cls, index, key=None, value=None, entity=None):
        """ Remove any nodes or relationships from an index that match a
        particular set of criteria. Allowed parameter combinations are:

        `key`, `value`, `entity`
            remove a specific node or relationship indexed under a given
            key-value pair

        `key`, `entity`
            remove a specific node or relationship indexed against a given key
            and with any value

        `entity`
            remove all occurrences of a specific node or relationship
            regardless of key or value

        :param cls: the type of indexed entity
        :type cls: :py:class:`Node <py2neo.neo4j.Node>` or
                   :py:class:`Relationship <py2neo.neo4j.Relationship>`
        :param index: index or index name
        :type index: :py:class:`Index <py2neo.neo4j.Index>` or :py:class:`str`
        :param key: index entry key
        :type key: :py:class:`str`
        :param value: index entry value
        :param entity: node or relationship to remove from the index
        :type entity: concrete or reference
        :return: batch request object
        """
        index = self._index(cls, index)
        if key and value and entity:
            uri = self._uri_for(index, key, value, entity._id)
        elif key and entity:
            uri = self._uri_for(index, key, entity._id)
        elif entity:
            uri = self._uri_for(index, entity._id)
        else:
            raise TypeError("Illegal parameter combination for index removal")
        return self.append_delete(uri)

    ### START OF DEPRECATED METHODS ###

    @deprecated("WriteBatch.add_indexed_node is deprecated, "
                "use add_to_index instead")
    def add_indexed_node(self, index, key, value, node):
        return self.add_to_index(Node, index, key, value, node)

    @deprecated("WriteBatch.add_indexed_relationship is deprecated, "
                "use add_to_index instead")
    def add_indexed_relationship(self, index, key, value, relationship):
        return self.add_to_index(Relationship, index, key, value, relationship)

    @deprecated("WriteBatch.add_indexed_node_or_fail is deprecated, "
                "use add_to_index_or_fail instead")
    def add_indexed_node_or_fail(self, index, key, value, node):
        return self.add_to_index_or_fail(Node, index, key, value, node)

    @deprecated("WriteBatch.add_indexed_relationship_or_fail is deprecated, "
                "use add_to_index_or_fail instead")
    def add_indexed_relationship_or_fail(self, index, key, value, relationship):
        return self.add_to_index_or_fail(Relationship, index, key, value,
                                         relationship)

    @deprecated("WriteBatch.create_indexed_node_or_fail is deprecated, "
                "use create_in_index_or_fail instead")
    def create_indexed_node_or_fail(self, index, key, value, properties=None):
        self._assert_can_create_or_fail()
        abstract = properties or {}
        return self.create_in_index_or_fail(Node, index, key, value, abstract)

    @deprecated("WriteBatch.create_indexed_relationship_or_fail is deprecated, "
                "use create_in_index_or_fail instead")
    def create_indexed_relationship_or_fail(self, index, key, value,
                                            start_node, type_, end_node,
                                            properties=None):
        self._assert_can_create_or_fail()
        if properties:
            abstract = _rel(start_node, (type_, properties), end_node)
        else:
            abstract = _rel(start_node, type_, end_node)
        return self.create_in_index_or_fail(Relationship, index, key, value,
                                            abstract)

    @deprecated("WriteBatch.get_or_add_indexed_node is deprecated, "
                "use get_or_add_to_index instead")
    def get_or_add_indexed_node(self, index, key, value, node):
        self.get_or_add_to_index(Node, index, key, value, node)

    @deprecated("WriteBatch.get_or_add_indexed_relationship is deprecated, "
                "use get_or_add_to_index instead")
    def get_or_add_indexed_relationship(self, index, key, value, relationship):
        self.get_or_add_to_index(Relationship, index, key, value, relationship)

    @deprecated("WriteBatch.get_or_create_indexed_node is deprecated, "
                "use get_or_create_in_index instead")
    def get_or_create_indexed_node(self, index, key, value, properties=None):
        abstract = properties or {}
        return self.get_or_create_in_index(Node, index, key, value, abstract)

    @deprecated("WriteBatch.get_or_create_indexed_relationship is deprecated, "
                "use get_or_create_indexed instead")
    def get_or_create_indexed_relationship(self, index, key, value, start_node,
                                           type_, end_node, properties=None):
        if properties:
            abstract = _rel(start_node, (type_, properties), end_node)
        else:
            abstract = _rel(start_node, type_, end_node)
        return self.get_or_create_in_index(Relationship, index, key, value,
                                           abstract)

    @deprecated("WriteBatch.remove_indexed_node is deprecated, "
                "use remove_indexed instead")
    def remove_indexed_node(self, index, key=None, value=None, node=None):
        return self.remove_from_index(Node, index, key, value, node)

    @deprecated("WriteBatch.remove_indexed_relationship is deprecated, "
                "use remove_indexed instead")
    def remove_indexed_relationship(self, index, key=None, value=None,
                                    relationship=None):
        return self.remove_from_index(Relationship, index, key, value,
                                      relationship)
