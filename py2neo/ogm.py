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
from py2neo.util import label_case, relationship_case, metaclass


class Property(object):

    def __init__(self, key=None):
        self.key = key

    def __get__(self, instance, owner):
        return instance.__subgraph__[self.key]

    def __set__(self, instance, value):
        instance.__subgraph__[self.key] = value


class Label(object):

    def __init__(self, name=None):
        self.name = name

    def __get__(self, instance, owner):
        return instance.__subgraph__.has_label(self.name)

    def __set__(self, instance, value):
        if value:
            instance.__subgraph__.add_label(self.name)
        else:
            instance.__subgraph__.remove_label(self.name)


class Related(object):
    """ Represents a set of relationships from a single start node to
    (potentially) multiple end nodes.
    """

    def __init__(self, related_class, relationship_type=None):
        self.related_class = related_class
        self.relationship_type = relationship_type
        self.relationships = None

    def __get__(self, instance, owner):
        if self.relationships is None:
            if isinstance(self.related_class, type):
                related_class = self.related_class
            else:
                module_name, _, class_name = self.related_class.rpartition(".")
                if not module_name:
                    module_name = instance.__class__.__module__
                module = __import__(module_name, fromlist=".")
                related_class = getattr(module, class_name)
            self.relationships = RelationshipSet(instance, self.relationship_type, related_class)
        return self.relationships


class RelationshipSet(object):

    def __init__(self, subject, relationship_type, related_class):
        self.subject = subject
        self.relationship_type = relationship_type
        self.related_class = related_class
        self._related_objects = None

    def __iter__(self):
        self._refresh()
        return iter(self._related_objects)

    def _refresh(self):
        if self._related_objects is None:
            self.pull()

    def add(self, item, properties, **kwproperties):
        self._related_objects[item] = dict(properties, **kwproperties)

    def remove(self, item):
        del self._related_objects[item]

    def pull(self):
        self._related_objects = {}
        subject = self.subject
        for r in subject.__graph__.match(subject.__subgraph__, self.relationship_type):
            related_object = self.related_class.wrap(r.end_node())
            self._related_objects[related_object] = dict(r)

    def push(self):
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
        attributes.setdefault("__primarylabel__", name)
        attributes.setdefault("__primarykey__", "__id__")
        return super(GraphObjectMeta, mcs).__new__(mcs, name, bases, attributes)


@metaclass(GraphObjectMeta)
class GraphObject(object):
    __graph__ = None
    __primarylabel__ = None
    __primarykey__ = None
    __subgraph = None

    @property
    def __subgraph__(self):
        if self.__subgraph is None:
            self.__subgraph = Node(self.__primarylabel__)
        node = self.__subgraph
        if not hasattr(node, "__primarylabel__"):
            setattr(node, "__primarylabel__", self.__primarylabel__)
        if not hasattr(node, "__primarykey__"):
            setattr(node, "__primarykey__", self.__primarykey__)
        return node

    @property
    def __remote__(self):
        return self.__subgraph__.__remote__

    @classmethod
    def load_one(cls, primary_value):
        graph = cls.__graph__
        if graph is None:
            raise RuntimeError("No graph database defined for %s" % cls.__name__)
        primary_key = cls.__primarykey__
        if primary_key == "__id__":
            node = graph.evaluate("MATCH (a:%s) WHERE id(a)={x} RETURN a" %
                                  cypher_escape(cls.__primarylabel__), x=primary_value)
        else:
            node = graph.find_one(cls.__primarylabel__, primary_key, primary_value)
        return cls.wrap(node)

    @classmethod
    def wrap(cls, node):
        if node is None:
            return None
        inst = GraphObject()
        inst.__subgraph = node
        inst.__class__ = cls
        return inst

    @classmethod
    def load(cls, primary_values):
        graph = cls.__graph__
        primary_key = cls.__primarykey__
        if primary_key == "__id__":
            for record in graph.run("MATCH (a:%s) WHERE id(a) IN {x} RETURN a" %
                                    cypher_escape(cls.__primarylabel__), x=list(primary_values)):
                inst = GraphObject()
                inst.__subgraph = record["a"]
                inst.__class__ = cls
                yield inst
        else:
            for node in graph.find(cls.__primarylabel__, primary_key, tuple(primary_values)):
                inst = GraphObject()
                inst.__subgraph = node
                inst.__class__ = cls
                yield inst

    def __repr__(self):
        return "<%s %s>" % (self.__class__.__name__,
                            " ".join("%s=%r" % (k, getattr(self, k)) for k in dir(self)
                                     if not k.startswith("_") and not callable(getattr(self, k))))

    @property
    def __primaryvalue__(self):
        node = self.__subgraph__
        primary_key = self.__primarykey__
        if primary_key == "__id__":
            remote_node = remote(node)
            if remote_node:
                return remote_node._id
            else:
                return None
        else:
            return node[primary_key]

    def __db_create__(self, tx):
        tx.create(self.__subgraph__)

    def __db_merge__(self, tx):
        tx.merge(self.__subgraph__)

    def __db_delete__(self, tx):
        tx.delete(self.__subgraph__)

    def __db_pull__(self, graph):
        graph.pull(self.__subgraph__)

    def __db_push__(self, graph):
        graph.push(self.__subgraph__)
