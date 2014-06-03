#/usr/bin/env python
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

import logging
import sys

import pytest

from py2neo import neo4j, node
from py2neo.packages.httpstream import (NetworkAddressError, SocketError)

PY3K = sys.version_info[0] >= 3

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    level=logging.DEBUG,
)


def test_wrong_host_will_fail():
    graph = neo4j.Graph("http://localtoast:7474/db/data/")
    try:
        graph.resource.get()
    except NetworkAddressError:
        assert True
    else:
        assert False


def test_wrong_port_will_fail():
    graph = neo4j.Graph("http://localhost:7575/db/data/")
    try:
        graph.resource.get()
    except SocketError:
        assert True
    else:
        assert False


def test_wrong_path_will_fail():
    graph = neo4j.Graph("http://localhost:7474/foo/bar/")
    try:
        graph.resource.get()
    except neo4j.ClientError:
        assert True
    else:
        assert False


def test_can_use_graph_if_no_trailing_slash_supplied(graph):
    alice, = graph.create(node(name="Alice"))
    assert isinstance(alice, neo4j.Node)
    assert alice["name"] == "Alice"


class TestGraph(object):

    @pytest.fixture(autouse=True)
    def setup(self, graph):
        self.graph = graph

    def test_can_get_same_instance(self):
        graph_1 = neo4j.Graph(neo4j.DEFAULT_URI)
        graph_2 = neo4j.Graph(neo4j.DEFAULT_URI)
        assert graph_1 is graph_2

    def test_neo4j_version_format(self):
        version = self.graph.neo4j_version
        print(version)
        assert isinstance(version, tuple)
        assert len(version) == 4
        assert isinstance(version[0], int)
        assert isinstance(version[1], int)
        assert isinstance(version[2], int)

    def test_create_single_empty_node(self):
        a, = self.graph.create({})

    def test_get_node_by_id(self):
        a1, = self.graph.create({"foo": "bar"})
        a2 = self.graph.node(a1._id)
        assert a1 == a2

    def test_create_node_with_property_dict(self):
        node, = self.graph.create({"foo": "bar"})
        assert node["foo"] == "bar"

    def test_create_node_with_mixed_property_types(self):
        node, = self.graph.create(
            {"number": 13, "foo": "bar", "true": False, "fish": "chips"}
        )
        assert len(node.get_properties()) == 4
        assert node["fish"] == "chips"
        assert node["foo"] == "bar"
        assert node["number"] == 13
        assert not node["true"]

    def test_create_node_with_null_properties(self):
        node, = self.graph.create({"foo": "bar", "no-foo": None})
        assert node["foo"] == "bar"
        assert node["no-foo"] is None

    def test_create_multiple_nodes(self):
        nodes = self.graph.create(
                {},
                {"foo": "bar"},
                {"number": 42, "foo": "baz", "true": True},
                {"fish": ["cod", "haddock", "plaice"], "number": 109}
        )
        assert len(nodes) == 4
        assert len(nodes[0].get_properties()) == 0
        assert len(nodes[1].get_properties()) == 1
        assert nodes[1]["foo"] == "bar"
        assert len(nodes[2].get_properties()) == 3
        assert nodes[2]["number"] == 42
        assert nodes[2]["foo"] == "baz"
        assert nodes[2]["true"]
        assert len(nodes[3].get_properties()) == 2
        assert nodes[3]["fish"][0] == "cod"
        assert nodes[3]["fish"][1] == "haddock"
        assert nodes[3]["fish"][2] == "plaice"
        assert nodes[3]["number"] == 109

    def test_batch_get_properties(self):
        nodes = self.graph.create(
            {},
            {"foo": "bar"},
            {"number": 42, "foo": "baz", "true": True},
            {"fish": ["cod", "haddock", "plaice"], "number": 109}
        )
        props = self.graph.get_properties(*nodes)
        assert len(props) == 4
        assert len(props[0]) == 0
        assert len(props[1]) == 1
        assert props[1]["foo"] == "bar"
        assert len(props[2]) == 3
        assert props[2]["number"] == 42
        assert props[2]["foo"] == "baz"
        assert props[2]["true"]
        assert len(props[3]) == 2
        assert props[3]["fish"][0] == "cod"
        assert props[3]["fish"][1] == "haddock"
        assert props[3]["fish"][2] == "plaice"
        assert props[3]["number"] == 109

    def test_graph_class_aliases(self):
        assert issubclass(neo4j.GraphDatabaseService, neo4j.Graph)


class TestNewCreate(object):

    @pytest.fixture(autouse=True)
    def setup(self, graph):
        self.graph = graph

    def test_can_create_single_node(self):
        results = self.graph.create(
            {"name": "Alice"}
        )
        assert results is not None
        assert isinstance(results, list)
        assert len(results) == 1
        assert isinstance(results[0], neo4j.Node)
        assert "name" in results[0]
        assert results[0]["name"] == "Alice"

    def test_can_create_simple_graph(self):
        results = self.graph.create(
            {"name": "Alice"},
            {"name": "Bob"},
            (0, "KNOWS", 1)
        )
        assert results is not None
        assert isinstance(results, list)
        assert len(results) == 3
        assert isinstance(results[0], neo4j.Node)
        assert "name" in results[0]
        assert results[0]["name"] == "Alice"
        assert isinstance(results[1], neo4j.Node)
        assert "name" in results[1]
        assert results[1]["name"] == "Bob"
        assert isinstance(results[2], neo4j.Relationship)
        assert results[2].type == "KNOWS"
        assert results[2].start_node == results[0]
        assert results[2].end_node == results[1]

    def test_can_create_simple_graph_with_rel_data(self):
        results = self.graph.create(
            {"name": "Alice"},
            {"name": "Bob"},
            (0, "KNOWS", 1, {"since": 1996})
        )
        assert results is not None
        assert isinstance(results, list)
        assert len(results) == 3
        assert isinstance(results[0], neo4j.Node)
        assert "name" in results[0]
        assert results[0]["name"] == "Alice"
        assert isinstance(results[1], neo4j.Node)
        assert "name" in results[1]
        assert results[1]["name"] == "Bob"
        assert isinstance(results[2], neo4j.Relationship)
        assert results[2].type == "KNOWS"
        assert results[2].start_node == results[0]
        assert results[2].end_node == results[1]
        assert "since" in results[2]
        assert results[2]["since"] == 1996

    def test_can_create_graph_against_existing_node(self):
        ref_node, = self.graph.create({})
        results = self.graph.create(
            {"name": "Alice"},
            (ref_node, "PERSON", 0)
        )
        assert results is not None
        assert isinstance(results, list)
        assert len(results) == 2
        assert isinstance(results[0], neo4j.Node)
        assert "name" in results[0]
        assert results[0]["name"] == "Alice"
        assert isinstance(results[1], neo4j.Relationship)
        assert results[1].type == "PERSON"
        assert results[1].start_node == ref_node
        assert results[1].end_node == results[0]
        self.graph.delete(results[1], results[0])
        ref_node.delete()

    def test_fails_on_bad_reference(self):
        with pytest.raises(Exception):
            self.graph.create({"name": "Alice"}, (0, "KNOWS", 1))

    def test_can_create_big_graph(self):
        size = 40
        nodes = [
            {"number": i}
            for i in range(size)
        ]
        results = self.graph.create(*nodes)
        assert results is not None
        assert isinstance(results, list)
        assert len(results) == size
        for i in range(size):
            assert isinstance(results[i], neo4j.Node)


class TestMultipleNode(object):

    flintstones = [
        {"name": "Fred"},
        {"name": "Wilma"},
        {"name": "Barney"},
        {"name": "Betty"}
    ]

    @pytest.fixture(autouse=True)
    def setup(self, graph):
        self.gdb = graph
        self.ref_node, = self.gdb.create({})
        self.nodes = self.gdb.create(*self.flintstones)

    def test_is_created(self):
        assert self.nodes is not None
        assert len(self.nodes) == len(self.flintstones)

    def test_has_correct_properties(self):
        assert [
            node.get_properties()
            for node in self.nodes
        ] == self.flintstones

    def test_create_relationships(self):
        rels = self.gdb.create(*[
            (self.ref_node, "FLINTSTONE", node)
            for node in self.nodes
        ])
        self.gdb.delete(*rels)
        assert len(self.nodes) == len(rels)

    def tearDown(self):
        self.gdb.delete(*self.nodes)
        self.ref_node.delete()


class TestRelatedDelete(object):

    @pytest.fixture(autouse=True)
    def setup(self, graph):
        self.graph = graph
        self.recycling = []

    def test_can_delete_entire_subgraph(self):
        query = '''\
        CREATE (en {place: "England"}),
               (sc {place: "Scotland"}),
               (cy {place: "Wales"}),
               (fr {place: "France"}),
               (de {place: "Germany"}),
               (es {place: "Spain"}),
               (eng {lang: "English"}),
               (fre {lang: "French"}),
               (deu {lang: "German"}),
               (esp {lang: "Spanish"}),
               (A {name: "Alice"}),
               (A)-[:LIVES_IN]->(en),
               (A)-[:SPEAKS]->(eng),
               (B {name: "Bob"}),
               (B)-[:LIVES_IN]->(cy),
               (B)-[:SPEAKS]->(eng),
               (C {name: "Carlos"}),
               (C)-[:LIVES_IN]->(es),
               (C)-[:SPEAKS]->(esp),
               (D {name: "Dagmar"}),
               (D)-[:LIVES_IN]->(de),
               (D)-[:SPEAKS]->(deu),
               (E {name: "Elspeth"}),
               (E)-[:LIVES_IN]->(sc),
               (E)-[:SPEAKS]->(eng),
               (E)-[:SPEAKS]->(deu),
               (F {name: "François"}),
               (F)-[:LIVES_IN]->(fr),
               (F)-[:SPEAKS]->(eng),
               (F)-[:SPEAKS]->(fre),
               (G {name: "Gina"}),
               (G)-[:LIVES_IN]->(de),
               (G)-[:SPEAKS]->(eng),
               (G)-[:SPEAKS]->(fre),
               (G)-[:SPEAKS]->(deu),
               (G)-[:SPEAKS]->(esp),
               (H {name: "Hans"}),
               (H)-[:LIVES_IN]->(de),
               (H)-[:SPEAKS]->(deu)
        RETURN en, sc, cy, fr, de, es, eng, fre, deu, esp,
               A, B, C, D, E, F, G, H
        '''
        data = list(neo4j.CypherQuery(self.graph, query).execute())
        entities = data[0]
        for entity in entities:
            assert entity.exists
        alice = entities[10]
        alice.delete_related()
        for entity in entities:
            assert not entity.exists
