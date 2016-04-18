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


from py2neo.database import cypher_escape
from py2neo.types import Node, remote
from py2neo.util import label_case, relationship_case


class Property(object):

    def __init__(self, key=None):
        self.key = key

    def __get__(self, instance, owner):
        return instance.__db_node__[self.key]

    def __set__(self, instance, value):
        instance.__db_node__[self.key] = value


class Label(object):

    def __init__(self, name=None):
        self.name = name

    def __get__(self, instance, owner):
        return instance.__db_node__.has_label(self.name)

    def __set__(self, instance, value):
        if value:
            instance.__db_node__.add_label(self.name)
        else:
            instance.__db_node__.remove_label(self.name)


class Related(object):

    __related_node_class = None

    def __init__(self, related_node_class, relationship_type=None):
        self.__related_node_class = related_node_class
        self.relationship_type = relationship_type

    def __get__(self, instance, owner):
        return instance.__db_relationships__.setdefault(self.relationship_type, set())

    @property
    def related_node_class(self):
        if isinstance(self.__related_node_class, type):
            return self.__related_node_class
        else:
            return globals()[self.__related_node_class]

    def add(self, item):
        pass

    def remove(self, item):
        pass


class RelatedItems(object):

    pass


class GraphObjectMeta(type):

    def __new__(mcs, name, bases, attributes):
        related_attr = {}
        for attr_name, attr in list(attributes.items()):
            if isinstance(attr, Property):
                if attr.key is None:
                    attr.key = attr_name
            elif isinstance(attr, Label):
                if attr.name is None:
                    attr.name = label_case(attr_name)
            elif isinstance(attr, Related):
                if attr.relationship_type is None:
                    attr.relationship_type = relationship_case(attr_name)
                related_attr[attr.relationship_type] = attr
        attributes["__related_attr__"] = related_attr
        attributes.setdefault("__primary_label__", name)
        attributes.setdefault("__primary_key__", "__id__")
        return super().__new__(mcs, name, bases, attributes)


class GraphObject(metaclass=GraphObjectMeta):
    __graph__ = None
    __primary_label__ = None
    __primary_key__ = None

    __db_node = None
    __db_relationships = None

    @classmethod
    def load(cls, primary_value):
        graph = cls.__graph__
        # Label:key=value
        primary_key = cls.__primary_key__
        if primary_key == "__id__":
            node = graph.evaluate("MATCH (a:%s) WHERE id(a)={x}" %
                                  cypher_escape(cls.__primary_label__), x=primary_value)
        else:
            node = graph.find_one(cls.__primary_label__, primary_key, primary_value)
        if node is None:
            raise LookupError("Cannot load object")
        return cls.wrap(node)

    @classmethod
    def wrap(cls, node):
        graph = cls.__graph__
        inst = GraphObject()
        inst.__db_node = node
        inst.__db_relationships = {}
        for relationship in graph.match(node):
            related_nodes = inst.__db_relationships.setdefault(relationship.type(), set())
            related_nodes.add(relationship.end_node())
        inst.__class__ = cls
        return inst

    def __eq__(self, other):
        try:
            return self.__db_node__ == other.__db_node__
        except AttributeError:
            return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self.__db_node__)

    @property
    def __db_node__(self):
        if self.__db_node is None:
            self.__db_node = Node(self.__primary_label__)
        return self.__db_node

    @property
    def __db_relationships__(self):
        if self.__db_relationships is None:
            self.__db_relationships = {}
        return self.__db_relationships

    @property
    def __primary_value__(self):
        node = self.__db_node__
        primary_key = self.__primary_key__
        if primary_key == "__id__":
            remote_node = remote(node)
            if remote_node:
                return remote_node._id
            else:
                return None
        else:
            return node[primary_key]

    @property
    def __remote__(self):
        return self.__db_node__.__remote__

    def __db_create_node__(self, tx):
        tx.merge(self.__db_node__, self.__primary_label__, self.__primary_key__)

    def __db_create__(self, tx):
        self.__db_create_node__(tx)
        # related_nodes = set()
        # for _, nodes in self.__db_relationships.items():
        #     related_nodes |= nodes
        # for node in related_nodes:

    def __db_delete__(self, tx):
        # TODO: delete if not bound
        tx.delete(self.__db_node__)

    def __db_pull__(self, graph):
        graph.pull(self.__db_node__)

    def __db_push__(self, graph):
        graph.push(self.__db_node__)


class Person(GraphObject):
    __primary_key__ = "name"

    name = Property()
    year_of_birth = Property(key="born")

    acted_in = Related("Movie")
    directed = Related("Movie")
    produced = Related("Movie")


class Movie(GraphObject):
    __primary_key__ = "title"

    title = Property()
    tag_line = Property(key="tagline")
    year_of_release = Property(key="released")


def main():
    from py2neo import Graph
    GraphObject.__graph__ = Graph(host="graph.pub", https_port=7473, password="welcomebackwemissedyou")
    keanu = Person.load("Keanu Reeves")
    the_matrix = Movie.load("The Matrix")
    keanu.acted_in.add(the_matrix)
    print(keanu)


if __name__ == "__main__":
    main()
