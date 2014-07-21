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


import pytest

from py2neo import Graph, Relationship, WriteBatch


def test_can_get_relationship_by_id_when_cached(graph):
    _, _, relationship = graph.create({}, {}, (0, "KNOWS", 1))
    got = graph.relationship(relationship._id)
    assert got is relationship


def test_can_get_relationship_by_id_when_not_cached(graph):
    _, _, relationship = graph.create({}, {}, (0, "KNOWS", 1))
    Relationship.cache.clear()
    got = graph.relationship(relationship._id)
    assert got._id == relationship._id


def test_cannot_get_relationship_by_id_when_id_does_not_exist(graph):
    _, _, relationship = graph.create({}, {}, (0, "KNOWS", 1))
    rel_id = relationship._id
    graph.delete(relationship)
    Relationship.cache.clear()
    try:
        _ = graph.relationship(rel_id)
    except ValueError:
        assert True
    else:
        assert False


class TestIsolate(object):

    @pytest.fixture(autouse=True)
    def setup(self, graph):
        self.graph = graph
        Graph.auto_sync_properties = True

    def test_can_isolate_node(self):
        posse = self.graph.create(
            {"name": "Alice"},
            {"name": "Bob"},
            {"name": "Carol"},
            {"name": "Dave"},
            {"name": "Eve"},
            {"name": "Frank"},
            (0, "KNOWS", 1),
            (0, "KNOWS", 2),
            (0, "KNOWS", 3),
            (0, "KNOWS", 4),
            (2, "KNOWS", 0),
            (3, "KNOWS", 0),
            (4, "KNOWS", 0),
            (5, "KNOWS", 0),
        )
        alice = posse[0]
        friendships = list(alice.match())
        assert len(friendships) == 8
        alice.isolate()
        friendships = list(alice.match())
        assert len(friendships) == 0


class TestRelationship(object):

    @pytest.fixture(autouse=True)
    def setup(self, graph):
        self.graph = graph
        Graph.auto_sync_properties = True

    def test_create_relationship_to(self):
        alice, bob = self.graph.create(
            {"name": "Alice"}, {"name": "Bob"}
        )
        ab = alice.create_path("KNOWS", bob).relationships[0]
        assert ab is not None
        assert isinstance(ab, Relationship)
        assert ab.start_node == alice
        assert ab.type == "KNOWS"
        assert ab.end_node == bob

    def test_create_relationship_from(self):
        alice, bob = self.graph.create(
            {"name": "Alice"}, {"name": "Bob"}
        )
        ba = bob.create_path("LIKES", alice).relationships[0]
        assert ba is not None
        assert isinstance(ba, Relationship)
        assert ba.start_node == bob
        assert ba.type == "LIKES"
        assert ba.end_node == alice

    def test_getting_no_relationships(self):
        alice, = self.graph.create({"name": "Alice"})
        rels = list(alice.match())
        assert rels is not None
        assert isinstance(rels, list)
        assert len(rels) == 0

    def test_get_relationship(self):
        alice, bob, ab = self.graph.create({"name": "Alice"}, {"name": "Bob"}, (0, "KNOWS", 1))
        rel = self.graph.relationship(ab._id)
        assert rel == ab

    def test_create_relationship_with_properties(self):
        alice, bob = self.graph.create(
            {"name": "Alice"}, {"name": "Bob"}
        )
        ab = alice.create_path(("KNOWS", {"since": 1999}), bob).relationships[0]
        assert ab is not None
        assert isinstance(ab, Relationship)
        assert ab.start_node == alice
        assert ab.type == "KNOWS"
        assert ab.end_node == bob
        assert len(ab) == 1
        assert ab["since"] == 1999
        assert ab.get_properties() == {"since": 1999}
        ab["foo"] = "bar"
        assert len(ab) == 2
        assert ab["foo"] == "bar"
        assert ab.get_properties() == {"since": 1999, "foo": "bar"}
        del ab["foo"]
        assert len(ab) == 1
        assert ab["since"] == 1999
        assert ab.get_properties() == {"since": 1999}
        ab.delete_properties()
        assert len(ab) == 0
        assert ab.get_properties() == {}


class TestRelate(object):

    @pytest.fixture(autouse=True)
    def setup(self, graph):
        self.graph = graph
        Graph.auto_sync_properties = True

    def test_relate(self):
        alice, bob = self.graph.create(
            {"name": "Alice"}, {"name": "Bob"}
        )
        rel = alice.get_or_create_path("KNOWS", bob).relationships[0]
        assert rel is not None
        assert isinstance(rel, Relationship)
        assert rel.start_node == alice
        assert rel.type == "KNOWS"
        assert rel.end_node == bob

    def test_repeated_relate(self):
        alice, bob = self.graph.create(
            {"name": "Alice"}, {"name": "Bob"}
        )
        rel1 = alice.get_or_create_path("KNOWS", bob).relationships[0]
        assert rel1 is not None
        assert isinstance(rel1, Relationship)
        assert rel1.start_node == alice
        assert rel1.type == "KNOWS"
        assert rel1.end_node == bob
        rel2 = alice.get_or_create_path("KNOWS", bob).relationships[0]
        assert rel1  == rel2
        rel3 = alice.get_or_create_path("KNOWS", bob).relationships[0]
        assert rel1 == rel3

    def test_relate_with_no_end_node(self):
        alice, = self.graph.create(
            {"name": "Alice"}
        )
        rel = alice.get_or_create_path("KNOWS", None).relationships[0]
        assert rel is not None
        assert isinstance(rel, Relationship)
        assert rel.start_node == alice
        assert rel.type == "KNOWS"

    def test_relate_with_data(self):
        alice, bob = self.graph.create(
            {"name": "Alice"}, {"name": "Bob"}
        )
        rel = alice.get_or_create_path(("KNOWS", {"since": 2006}), bob).relationships[0]
        assert rel is not None
        assert isinstance(rel, Relationship)
        assert rel.start_node == alice
        assert rel.type == "KNOWS"
        assert rel.end_node == bob
        assert "since" in rel
        assert rel["since"] == 2006

    def test_relate_with_null_data(self):
        alice, bob = self.graph.create(
            {"name": "Alice"}, {"name": "Bob"}
        )
        rel = alice.get_or_create_path(("KNOWS", {"since": 2006, "dummy": None}), bob).relationships[0]
        assert rel is not None
        assert isinstance(rel, Relationship)
        assert rel.start_node == alice
        assert rel.type == "KNOWS"
        assert rel.end_node == bob
        assert "since" in rel
        assert rel["since"] == 2006
        assert rel["dummy"] is None

    def test_repeated_relate_with_data(self):
        alice, bob = self.graph.create(
            {"name": "Alice"}, {"name": "Bob"}
        )
        rel1 = alice.get_or_create_path(("KNOWS", {"since": 2006}), bob).relationships[0]
        assert rel1 is not None
        assert isinstance(rel1, Relationship)
        assert rel1.start_node == alice
        assert rel1.type == "KNOWS"
        assert rel1.end_node == bob
        rel2 = alice.get_or_create_path(("KNOWS", {"since": 2006}), bob).relationships[0]
        assert rel1 == rel2
        rel3 = alice.get_or_create_path(("KNOWS", {"since": 2006}), bob).relationships[0]
        assert rel1 == rel3

    # disabled test known to fail due to server issues
    #
    #def test_relate_with_list_data(self):
    #    alice, bob = self.graph.create(
    #        {"name": "Alice"}, {"name": "Bob"}
    #    )
    #    rel, = self.graph.get_or_create_relationships((alice, "LIKES", bob, {"reasons": ["looks", "wealth"]}))
    #    assert rel is not None
    #    assert isinstance(rel, Relationship)
    #    assert rel.start_node == alice
    #    self.assertEqual("LIKES", rel.type)
    #    assert rel.end_node == bob
    #    self.assertTrue("reasons" in rel)
    #    self.assertEqual("looks", rel["reasons"][0])
    #    self.assertEqual("wealth", rel["reasons"][1])

    def test_complex_relate(self):
        alice, bob, carol, dave = self.graph.create(
            {"name": "Alice"}, {"name": "Bob"},
            {"name": "Carol"}, {"name": "Dave"}
        )
        batch = WriteBatch(self.graph)
        batch.get_or_create_path(alice, ("IS~MARRIED~TO", {"since": 1996}), bob)
        #batch.get_or_create((alice, "DISLIKES", carol, {"reasons": ["youth", "beauty"]}))
        batch.get_or_create_path(alice, ("DISLIKES!", {"reason": "youth"}), carol)
        rels1 = batch.submit()
        assert rels1 is not None
        assert len(rels1) == 2
        batch = WriteBatch(self.graph)
        batch.get_or_create_path(bob, ("WORKS WITH", {"since": 2004, "company": "Megacorp"}), carol)
        #batch.get_or_create((alice, "DISLIKES", carol, {"reasons": ["youth", "beauty"]}))
        batch.get_or_create_path(alice, ("DISLIKES!", {"reason": "youth"}), carol)
        batch.get_or_create_path(bob, ("WORKS WITH", {"since": 2009, "company": "Megacorp"}), dave)
        rels2 = batch.submit()
        assert rels2 is not None
        assert len(rels2) == 3
        assert rels1[1] == rels2[1]
