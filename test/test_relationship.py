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


from py2neo import Graph, Node, Relationship, size
from py2neo.packages.httpstream import ClientError
from test.util import Py2neoTestCase


class DodgyClientError(ClientError):
    status_code = 499


class RelationshipTestCase(Py2neoTestCase):

    def test_can_get_all_relationship_types(self):
        types = self.graph.relationship_types
        assert isinstance(types, frozenset)
        
    def test_can_get_relationship_by_id_when_cached(self):
        a = Node()
        b = Node()
        r = Relationship(a, "TO", b)
        self.graph.create(r)
        got = self.graph.relationship(r.remote._id)
        assert got is r
        
    def test_can_get_relationship_by_id_when_not_cached(self):
        a = Node()
        b = Node()
        r = Relationship(a, "TO", b)
        self.graph.create(r)
        Relationship.cache.clear()
        got = self.graph.relationship(r.remote._id)
        assert got.remote._id == r.remote._id
        
    def test_relationship_cache_is_thread_local(self):
        import threading
        a = Node()
        b = Node()
        r = Relationship(a, "TO", b)
        self.graph.create(r)
        assert r.remote.uri in Relationship.cache
        other_relationship_cache_keys = []
    
        def check_cache():
            other_relationship_cache_keys.extend(Relationship.cache.keys())
    
        thread = threading.Thread(target=check_cache)
        thread.start()
        thread.join()
    
        assert r.remote.uri in Relationship.cache
        assert r.remote.uri not in other_relationship_cache_keys
        
    def test_cannot_get_relationship_by_id_when_id_does_not_exist(self):
        a = Node()
        b = Node()
        r = Relationship(a, "TO", b)
        self.graph.create(r)
        rel_id = r.remote._id
        self.graph.delete(r)
        Relationship.cache.clear()
        with self.assertRaises(IndexError):
            _ = self.graph.relationship(rel_id)

    def test_getting_no_relationships(self):
        alice = Node(name="Alice")
        self.graph.create(alice)
        rels = list(self.graph.match(alice))
        assert rels is not None
        assert isinstance(rels, list)
        assert len(rels) == 0

    def test_graph(self):
        a = Node()
        b = Node()
        r = Relationship(a, "TO", b)
        self.graph.create(r)
        assert r.remote
        assert r.remote.graph == Graph("http://localhost:7474/db/data/")

    def test_only_one_relationship_in_a_relationship(self):
        rel = Relationship({}, "KNOWS", {})
        assert size(rel) == 1

    def test_relationship_equality_with_none(self):
        rel = Relationship({}, "KNOWS", {})
        none = None
        assert rel != none

    def test_relationship_default_type(self):
        assert Relationship.default_type() == "TO"

    def test_relationship_subclass_default_type(self):
        class Knows(Relationship):
            pass
        assert Knows.default_type() == "KNOWS"
