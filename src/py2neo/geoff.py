#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2011-2012 Nigel Small
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

""" Geoff is a textual interchange format for graph data, designed with Neo4j
    in mind.

    Note: This module will only work against server version 1.8.1 and above.

    Full Geoff Syntax
    -----------------

    ::

        geoff          := [element (_ element)*]
        element        := path | index_entry | comment

        path           := node (forward_path | reverse_path)* [_ property_map]
        forward_path   := "-" relationship "->" node
        reverse_path   := "<-" relationship "-" node

        index_entry    := forward_entry | reverse_entry | postfix_entry
        forward_entry  := "|" ~ index_name _ property_pair ~ "|" "=>" node
        reverse_entry  := node "<=" "|" ~ index_name _ property_pair ~ "|"
        postfix_entry  := node "<=" "|" ~ index_name ~ "|" _ property_pair
        index_name     := name | JSON_STRING

        comment        := "/*" (((any text excluding sequence "*/"))) "*/"

        node           := named_node | anonymous_node
        named_node     := "(" ~ node_name [_ property_map] ~ ")"
        anonymous_node := "(" ~ property_map ~ ")"
        relationship   := "[" ~ ":" type [_ property_map] ~ "]"
        property_pair  := "{" ~ key_value ~ "}"
        property_map   := "{" ~ [key_value (~ "," ~ key_value)* ~] "}"
        node_name      := name | JSON_STRING
        name           := (ALPHA | DIGIT | "_")+
        type           := name | JSON_STRING
        key_value      := key ~ ":" ~ value
        key            := name | JSON_STRING
        value          := array | JSON_STRING | JSON_NUMBER | JSON_BOOLEAN | JSON_NULL

        array          := empty_array | string_array | numeric_array | boolean_array
        empty_array    := "[" ~ "]"
        string_array   := "[" ~ JSON_STRING (~ "," ~ JSON_STRING)* ~ "]"
        numeric_array  := "[" ~ JSON_NUMBER (~ "," ~ JSON_NUMBER)* ~ "]"
        boolean_array  := "[" ~ JSON_BOOLEAN (~ "," ~ JSON_BOOLEAN)* ~ "]"

        * Mandatory whitespace is represented by "_" and optional whitespace by "~"
"""

from __future__ import absolute_import, division, print_function, unicode_literals

import json
import logging
import re

from . import neo4j, rest

logger = logging.getLogger(__name__)


class GeoffError(SyntaxError):

    pass


class Subgraph(object):

    @classmethod
    def from_xml(cls, xml):
        """ Convert XML into a geoff subgraph a la conversion page.
        """
        pass
    
    def __init__(self, source):
        """ Create a subgraph from Geoff source.
        """
        self._source = source
        parser = _Parser(self._source)
        self._nodes, self._rels, self._index_entries = parser.parse()

    @property
    def source(self):
        return self._source

    @property
    def nodes(self):
        return dict(self._nodes)

    @property
    def relationships(self):
        return list(self._rels)

    @property
    def index_entries(self):
        return dict(self._index_entries)

    @property
    def indexed_nodes(self):
        """ Return the set of nodes which have one or more index entries
            pointing to them.
        """
        return dict(
            (entry.node.name, entry.node)
            for entry in self._index_entries.values()
        )

    @property
    def related_nodes(self):
        """ Return the set of nodes which are involved in at least one
            relationship.
        """
        nodes = dict(
            (rel.start_node.name, rel.start_node)
            for rel in self._rels
        )
        nodes.update(dict(
            (rel.end_node.name, rel.end_node)
            for rel in self._rels
        ))
        return nodes

    @property
    def odd_nodes(self):
        """ Return the set of nodes which have no index entries pointing to
            them and are involved in no relationships.
        """
        return dict(
            (name, node)
            for name, node in self._nodes.items()
            if name not in self.indexed_nodes
            if name not in self.related_nodes
        )

    def _get_relationship_query(self, unique):
        # will only work in 1.8.1 and above
        start, create, set, output_names, params = [], [], [], [], {}
        # determine query inputs
        input_names, input_entries = list(self.indexed_nodes.keys()), []
        for name in input_names:
            entry = [
                entry
                for entry in self._index_entries.values()
                if entry.node.name == name
            ][0]
            input_entries.append(entry)
        #
        def node_pattern(i, name):
            if name in input_names:
                return "(in{0})".format(input_names.index(name))
            elif name in output_names:
                return "(out{0})".format(output_names.index(name))
            else:
                try:
                    params["sp" + str(i)] = self._nodes[name].properties
                except KeyError:
                    raise KeyError("Node '{0}' not found".format(name))
                output_names.append(name)
                return "(out{0} {{{1}}})".format(output_names.index(name), "sp" + str(i))
            #
        def rel_pattern(i, type_, properties):
            if properties:
                params["rp" + str(i)] = properties
                return "-[:`{0}` {{{1}}}]->".format(type_, "rp" + str(i))
            else:
                return "-[:`{0}`]->".format(type_)
            #
        # build start clause from inputs
        for i, entry in enumerate(input_entries):
            start.append("in{0} = node:{1}(`{2}`={{val{0}}})".format(i, entry.index_name, entry.key))
            params["val{0}".format(i)] = entry.value
            set.append("SET in{0} = {{pa{0}}}".format(i))
            params["pa{0}".format(i)] = entry.node.properties
        for i, rel in enumerate(self._rels):
            # build and append pattern
            create.append(node_pattern(i, rel.start_node.name) + \
                          rel_pattern(i, rel.type, rel.properties) + \
                          node_pattern(i, rel.end_node.name)
            )
        if start:
            query = "START {0}\n{1} {2}".format(
                ",\n      ".join(start),
                "CREATE UNIQUE" if unique else "CREATE",
                ",\n              ".join(create),
            )
        else:
            query = "CREATE {0}".format(
                ",\n              ".join(create),
            )
        if set:
            query += "".join("\n" + line for line in set)
        if output_names:
            query += "\nRETURN {0}".format(
                ",\n       ".join("out{0}".format(i) for i in range(len(output_names))),
            )
        #print(query)
        #print(params)
        return query, params, output_names

    def _execute_load_batch(self, graph_db, unique):
        # build batch request
        batch = neo4j.WriteBatch(graph_db)
        # 1. indexed nodes
        index_entries = list(self.index_entries.values())
        for entry in index_entries:
            batch.get_or_create_indexed_node(entry.index_name, entry.key, entry.value, entry.node.properties)
        # 2. related nodes
        if self._rels:
            query, params, related_names = self._get_relationship_query(unique)
            batch._post(batch._cypher_uri, {"query": query, "params": params})
        else:
            related_names = []
        # 3. odd nodes
        odd_names = list(self.odd_nodes.keys())
        for name in odd_names:
            batch.create_node(self._nodes[name].properties)
        # submit batch unless empty (in which case bail out and return nothing)
        if batch:
            try:
                responses = batch._submit()
            except rest.BadRequest as err:
                if err.exception == "UniquePathNotUniqueException":
                    err = GeoffError("Duplicate relationships exist - "
                                     "cannot merge")
                raise err
        else:
            return {}
        # parse response and build return value
        return_nodes = {}
        # 1. unique_nodes
        for i, entry in enumerate(index_entries):
            response = responses.pop(0)
            return_nodes[entry.node.name] = graph_db._resolve(response.body, response.status)
        # 2. related nodes
        if self._rels:
            data = responses.pop(0).body["data"]
            if data:
                for i, value in enumerate(data[0]):
                    value = graph_db._resolve(value)
                    return_nodes[related_names[i]] = graph_db._resolve(value)
        # 3. odd nodes
        for i, name in enumerate(odd_names):
            response = responses.pop(0)
            return_nodes[name] = graph_db._resolve(response.body, response.status)
        return return_nodes

    def insert_into(self, graph_db):
        """ Insert subgraph into graph database using Cypher CREATE.
        """
        return self._execute_load_batch(graph_db, False)

    def merge_into(self, graph_db):
        """ Merge subgraph into graph database using Cypher CREATE UNIQUE.
        """
        return self._execute_load_batch(graph_db, True)


class _Parser(object):

    JSON_BOOLEAN = re.compile(r'(true|false)', re.IGNORECASE)
    JSON_NUMBER  = re.compile(r'(-?(0|[1-9]\d*)(\.\d+)?(e[+-]?\d+)?)', re.IGNORECASE)
    JSON_STRING  = re.compile(r'''(".*?(?<!\\)")''')
    NAME         = re.compile(r'(\w+)', re.LOCALE | re.UNICODE)
    WHITESPACE   = re.compile(r'(\s*)')

    def __init__(self, source):
        self.source = source       # original source data
        self.n = 0                 # pointer to next position to be parsed

    def peek(self, length=1):
        return self.source[self.n:self.n + length]

    def parse(self):
        # FIRST PASS - work through source, extracting recognised elements
        self.n = 0
        elements = []   # temporary store for extracted elements
        self.parse_pattern(self.WHITESPACE)
        while self.n < len(self.source):
            element = self.parse_element()
            if isinstance(element, dict):
                if elements:
                    elements[-1].properties = element
                else:
                    raise GeoffError("Property map cannot occur as first element")
            elif isinstance(element, tuple):
                elements.extend(element)
            elif element is not None:
                elements.append(element)
            self.parse_pattern(self.WHITESPACE)
        # SECOND PASS - consolidate into collections of similar elements
        nodes, rels, index_entries = {}, [], {}
        def set_node(name, node):
            if name in nodes:
                nodes[name].properties.update(node.properties)
            else:
                nodes[name] = node
        for element in elements:
            if isinstance(element, AbstractNode):
                set_node(element.name, element)
            elif isinstance(element, AbstractRelationship):
                set_node(element.start_node.name, element.start_node)
                set_node(element.end_node.name, element.end_node)
                element.start_node = nodes[element.start_node.name]
                element.end_node = nodes[element.end_node.name]
                rels.append(element)
            elif isinstance(element, AbstractIndexEntry):
                set_node(element.node.name, element.node)
                element.node = nodes[element.node.name]
                key = (element.index_name, element.key, element.value, element.node.name)
                index_entries[key] = element
            else:
                raise AssertionError("Unknown element type '{0}'".format(type(element)))
        return nodes, rels, index_entries

    def parse_pattern(self, pattern):
        m = pattern.match(self.source, self.n)
        if m:
            self.n += len(m.group(0))
            return m.group(0)
        else:
            raise GeoffError("Unexpected character at position {0}".format(self.n))

    def parse_literal(self, literal):
        len_literal = len(literal)
        test = self.source[self.n:self.n + len_literal]
        if test == literal:
            self.n += len_literal
            return literal
        else:
            raise GeoffError("Unexpected character at position {0}".format(self.n))

    def parse_element(self):
        element = None
        next_char = self.peek()
        if next_char == "(":
            node = self.parse_node()
            if self.peek(2) == "<=":
                # index entry
                self.parse_literal("<=")
                index_name, key, value = self.read_index_point()
                element = AbstractIndexEntry(index_name, key, value, node)
            else:
                # path
                rels = []
                while not self.parse_pattern(self.WHITESPACE):
                    next_char = self.peek()
                    if next_char == "-":
                        rel = self.parse_forward_path(node)
                        node = rel.end_node
                        rels.append(rel)
                    elif next_char == "<":
                        rel = self.parse_reverse_path(node)
                        node = rel.start_node
                        rels.append(rel)
                    else:
                        raise GeoffError("Unexpected character '{0}' at position {1}".format(next_char, self.n))
                if rels:
                    element = tuple(rels)
                else:
                    element = node
        elif next_char == "|":
            index_name, key, value = self.read_index_point()
            self.parse_literal("=>")
            node = self.parse_node()
            element = AbstractIndexEntry(index_name, key, value, node)
        elif next_char == "/":
            self.parse_comment()
        elif next_char == "{":
            element = self.parse_properties()
        else:
            raise GeoffError("Unexpected character '{0}' at position {1}".format(next_char, self.n))
        return element

    def parse_node(self):
        self.parse_literal("(")
        self.parse_pattern(self.WHITESPACE)
        next_char = self.peek()
        if next_char == "{":
            node = AbstractNode(None, self.parse_properties())
        else:
            name = self.parse_name()
            if not self.parse_pattern(self.WHITESPACE):
                node = AbstractNode(name, None)
            else:
                node = AbstractNode(name, self.parse_properties())
        self.parse_pattern(self.WHITESPACE)
        self.parse_literal(")")
        return node

    def parse_name(self):
        if self.peek() == "\"":
            return self.parse_json_pattern(self.JSON_STRING)
        else:
            return self.parse_pattern(self.NAME)

    def parse_json_pattern(self, pattern):
        return json.loads(self.parse_pattern(pattern))

    def parse_properties(self):
        properties = []
        self.parse_literal("{")
        self.parse_pattern(self.WHITESPACE)
        if self.peek() != "}":
            properties.append(self.parse_key_value_pair())
            self.parse_pattern(self.WHITESPACE)
            while self.peek() == ",":
                self.parse_literal(",")
                self.parse_pattern(self.WHITESPACE)
                properties.append(self.parse_key_value_pair())
                self.parse_pattern(self.WHITESPACE)
        self.parse_literal("}")
        return dict(properties)

    def parse_key_value_pair(self):
        key = self.parse_name()
        self.parse_pattern(self.WHITESPACE)
        self.parse_literal(":")
        self.parse_pattern(self.WHITESPACE)
        value = self.parse_json_value()
        return key, value

    def parse_json_value(self):
        next_char = self.peek()
        if next_char == "[":
            return self.parse_array()
        elif next_char == '"':
            return self.parse_json_pattern(self.JSON_STRING)
        elif next_char in "-0123456789":
            return self.parse_json_pattern(self.JSON_NUMBER)
        elif next_char in "tf":
            return self.parse_json_pattern(self.JSON_BOOLEAN)
        elif next_char == "n":
            self.parse_literal("null")
            return None
        else:
            raise GeoffError("Unexpected character '{0}' at position {1}".format(next_char, self.n))

    def parse_array(self):
        items = []
        self.parse_literal("[")
        self.parse_pattern(self.WHITESPACE)
        next_char = self.peek()
        if next_char != "]":
            if next_char == '"':
                value_pattern = self.JSON_STRING
            elif next_char in "-0123456789":
                value_pattern = self.JSON_NUMBER
            elif next_char in "tf":
                value_pattern = self.JSON_BOOLEAN
            else:
                raise SyntaxError("Unexpected")
            items.append(self.parse_json_pattern(value_pattern))
            self.parse_pattern(self.WHITESPACE)
            while self.peek() == ",":
                self.parse_literal(",")
                self.parse_pattern(self.WHITESPACE)
                items.append(self.parse_json_pattern(value_pattern))
                self.parse_pattern(self.WHITESPACE)
        self.parse_literal("]")
        return items

    def parse_forward_path(self, start_node):
        self.parse_literal("-")
        rel = self.parse_relationship()
        self.parse_literal("->")
        rel.start_node = start_node
        rel.end_node = self.parse_node()
        return rel

    def parse_reverse_path(self, end_node):
        self.parse_literal("<-")
        rel = self.parse_relationship()
        self.parse_literal("-")
        rel.start_node = self.parse_node()
        rel.end_node = end_node
        return rel

    def parse_relationship(self):
        self.parse_literal("[")
        self.parse_pattern(self.WHITESPACE)
        self.parse_literal(":")
        type = self.parse_name()
        self.parse_pattern(self.WHITESPACE)
        next_char = self.peek()
        if next_char == "{":
            rel = AbstractRelationship(type, self.parse_properties())
            self.parse_pattern(self.WHITESPACE)
        else:
            rel = AbstractRelationship(type, None)
        self.parse_literal("]")
        return rel

    def parse_comment(self):
        self.parse_literal("/*")
        m = self.n
        while self.n < len(self.source) and self.peek(2) != "*/":
            self.n += 1
        comment = self.source[m:self.n]
        self.n += 2
        return comment

    def read_index_point(self):
        self.parse_literal("|")
        self.parse_pattern(self.WHITESPACE)
        index_name = self.parse_name()
        self.parse_pattern(self.WHITESPACE)
        self.parse_literal("{")
        self.parse_pattern(self.WHITESPACE)
        key, value = self.parse_key_value_pair()
        self.parse_pattern(self.WHITESPACE)
        self.parse_literal("}")
        self.parse_pattern(self.WHITESPACE)
        self.parse_literal("|")
        return index_name, key, value


class AbstractNode(object):

    def __init__(self, name, properties=None):
        self.name = name
        self.properties = properties or {}

    def __eq__(self, other):
        return self.name == other.name and self.properties == other.properties

    def __ne__(self, other):
        return self.name != other.name or self.properties != other.properties

    def __repr__(self):
        if self.properties:
            return "{0}({1}, {2})".format(self.__class__.__name__, repr(self.name), repr(self.properties))
        else:
            return "{0}({1})".format(self.__class__.__name__, repr(self.name))

    def __str__(self):
        if self.properties:
            return "({0} {1})".format(self.name, json.dumps(self.properties, separators=(",", ":")))
        else:
            return "({0})".format(self.name)


class AbstractRelationship(object):

    def __init__(self, type, properties=None):
        self.start_node = None
        self.type = type
        self.end_node = None
        self.properties = properties or {}

    def __str__(self):
        if self.properties:
            return "{0}-[:{1} {2}]->{3}".format(self.start_node, self.type, json.dumps(self.properties, separators=(",", ":")), self.end_node)
        else:
            return "{0}-[:{1}]->{2}".format(self.start_node, self.type, self.end_node)


class AbstractIndexEntry(object):

    def __init__(self, index_name, key, value, node):
        self.index_name = index_name
        self.key = key
        self.value = value
        self.node = node

    def __repr__(self):
        return "|{0} {1}|=>{2}".format(self.index_name, json.dumps({self.key: self.value}, separators=(",", ":")), self.node)
