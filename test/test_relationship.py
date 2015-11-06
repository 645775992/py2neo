#!/usr/bin/env python
# -*- encoding: utf-8 -*-

# Copyright 2011-2015, Nigel Small
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


from py2neo import Graph, Node, Relationship, Rel, Rev, GraphError, ServiceRoot, BindError
from py2neo.packages.httpstream import ClientError, Resource as _Resource
from test.util import Py2neoTestCase
from test.compat import patch

import sys
PY2 = sys.version_info < (3,)


class DodgyClientError(ClientError):
    status_code = 499


class RelationshipTestCase(Py2neoTestCase):

    def test_rel_and_rev_hashes(self):
        assert hash(Rel("KNOWS")) == hash(Rel("KNOWS"))
        assert hash(Rel("KNOWS")) == -hash(Rev("KNOWS"))
        assert hash(Rel("KNOWS", well=True, since=1999)) == hash(Rel("KNOWS", since=1999, well=True))
        rel_1 = Node("KNOWS", since=1999)
        self.graph.create(rel_1)
        rel_2 = Node("KNOWS", since=1999)
        rel_2.bind(rel_1.uri)
        assert rel_1 is not rel_2
        assert hash(rel_1) == hash(rel_2)

    def test_can_get_all_relationship_types(self):
        types = self.graph.relationship_types
        assert isinstance(types, frozenset)
        
    def test_can_get_relationship_by_id_when_cached(self):
        _, _, relationship = self.graph.create({}, {}, (0, "KNOWS", 1))
        got = self.graph.relationship(relationship._id)
        assert got is relationship
        
    def test_can_get_relationship_by_id_when_not_cached(self):
        _, _, relationship = self.graph.create({}, {}, (0, "KNOWS", 1))
        Relationship.cache.clear()
        got = self.graph.relationship(relationship._id)
        assert got._id == relationship._id
        
    def test_rel_and_relationship_caches_are_thread_local(self):
        import threading
        _, _, relationship = self.graph.create({}, {}, (0, "KNOWS", 1))
        assert relationship.uri in Rel.cache
        assert relationship.uri in Relationship.cache
        other_rel_cache_keys = []
        other_relationship_cache_keys = []
    
        def check_cache():
            other_rel_cache_keys.extend(Rel.cache.keys())
            other_relationship_cache_keys.extend(Relationship.cache.keys())
    
        thread = threading.Thread(target=check_cache)
        thread.start()
        thread.join()
    
        assert relationship.uri in Rel.cache
        assert relationship.uri in Relationship.cache
        assert relationship.uri not in other_rel_cache_keys
        assert relationship.uri not in other_relationship_cache_keys
        
    def test_cannot_get_relationship_by_id_when_id_does_not_exist(self):
        _, _, relationship = self.graph.create({}, {}, (0, "KNOWS", 1))
        rel_id = relationship._id
        self.graph.delete(relationship)
        Relationship.cache.clear()
        with self.assertRaises(ValueError):
            _ = self.graph.relationship(rel_id)

    def test_getting_no_relationships(self):
        alice, = self.graph.create({"name": "Alice"})
        rels = list(self.graph.match(alice))
        assert rels is not None
        assert isinstance(rels, list)
        assert len(rels) == 0

    def test_get_relationship(self):
        alice, bob, ab = self.graph.create({"name": "Alice"}, {"name": "Bob"}, (0, "KNOWS", 1))
        rel = self.graph.relationship(ab._id)
        assert rel == ab
        
    def test_rel_cannot_have_multiple_types(self):
        with self.assertRaises(ValueError):
            Rel("LIKES", "HATES")

    def test_type_of_bound_rel_is_immutable(self):
        a, b, ab = self.graph.create({}, {}, (0, "KNOWS", 1))
        with self.assertRaises(AttributeError):
            ab.rel.type = "LIKES"

    def test_type_of_unbound_rel_is_mutable(self):
        ab = Rel("KNOWS")
        ab.type = "LIKES"
        assert ab.type == "LIKES"
        
    def test_type_of_bound_relationship_is_immutable(self):
        a, b, ab = self.graph.create({}, {}, (0, "KNOWS", 1))
        with self.assertRaises(AttributeError):
            ab.type = "LIKES"

    def test_type_of_unbound_relationship_is_mutable(self):
        ab = Relationship({}, "KNOWS", {})
        ab.type = "LIKES"
        assert ab.type == "LIKES"
        
    def test_changing_type_of_unbound_rel_mirrors_to_pair_rev(self):
        rel = Rel("KNOWS")
        assert rel.pair is None
        rev = -rel
        assert rel.pair is rev
        assert rev.pair is rel
        assert rel.type == "KNOWS"
        assert rev.type == "KNOWS"
        rel.type = "LIKES"
        assert rel.type == "LIKES"
        assert rev.type == "LIKES"
        
    def test_changing_type_of_unbound_rev_mirrors_to_pair_rel(self):
        rev = Rev("KNOWS")
        assert rev.pair is None
        rel = -rev
        assert rev.pair is rel
        assert rel.pair is rev
        assert rev.type == "KNOWS"
        assert rel.type == "KNOWS"
        rev.type = "LIKES"
        assert rev.type == "LIKES"
        assert rel.type == "LIKES"
        
    def test_service_root(self):
        a, b, ab = self.graph.create({}, {}, (0, "KNOWS", 1))
        assert ab.service_root == ServiceRoot("http://localhost:7474/")
        ab.rel.unbind()
        assert ab.service_root == ServiceRoot("http://localhost:7474/")
        a.unbind()
        assert ab.service_root == ServiceRoot("http://localhost:7474/")
        b.unbind()
        with self.assertRaises(BindError):
            _ = ab.service_root

    def test_graph(self):
        a, b, ab = self.graph.create({}, {}, (0, "KNOWS", 1))
        assert ab.graph == Graph("http://localhost:7474/db/data/")
        ab.rel.unbind()
        assert ab.graph == Graph("http://localhost:7474/db/data/")
        a.unbind()
        assert ab.graph == Graph("http://localhost:7474/db/data/")
        b.unbind()
        with self.assertRaises(BindError):
            _ = ab.graph

    def test_rel_never_equals_none(self):
        rel = Rel("KNOWS")
        none = None
        assert rel != none
        
    def test_only_one_relationship_in_a_relationship(self):
        rel = Relationship({}, "KNOWS", {})
        assert rel.size == 1
        
    def test_relationship_requires_a_triple(self):
        with self.assertRaises(TypeError):
            Relationship({})

    def test_relationship_repr(self):
        alice = Node("Person", name="Alice")
        bob = Node("Person", name="Bob")
        relationship = Relationship(alice, "KNOWS", bob)
        if PY2:
            assert repr(relationship) == "<Relationship type=u'KNOWS' properties={}>"
        else:
            assert repr(relationship) == "<Relationship type='KNOWS' properties={}>"
        self.graph.create(relationship)
        if PY2:
            assert repr(relationship) == ("<Relationship graph=u'http://localhost:7474/db/data/' "
                                          "ref=u'%s' start=u'%s' end=u'%s' type=u'KNOWS' "
                                          "properties={}>" % (relationship.ref, alice.ref, bob.ref))
        else:
            assert repr(relationship) == ("<Relationship graph='http://localhost:7474/db/data/' "
                                          "ref='%s' start='%s' end='%s' type='KNOWS' "
                                          "properties={}>" % (relationship.ref, alice.ref, bob.ref))

    def test_unbound_rel_repr(self):
        rel = Rel("KNOWS", since=1999)
        assert repr(rel) == "<Rel type='KNOWS' properties={'since': 1999}>"

    def test_rel_repr(self):
        alice = Node("Person", name="Alice")
        bob = Node("Person", name="Bob")
        relationship = Relationship(alice, "KNOWS", bob)
        self.graph.create(relationship)
        rel = relationship.rel
        if PY2:
            assert repr(rel) == ("<Rel graph=u'http://localhost:7474/db/data/' ref=u'%s' "
                                 "type=u'KNOWS' properties={}>" % rel.ref)
        else:
            assert repr(rel) == ("<Rel graph='http://localhost:7474/db/data/' ref='%s' "
                                 "type='KNOWS' properties={}>" % rel.ref)

    def test_unbound_rev_repr(self):
        rev = Rev("KNOWS", since=1999)
        assert repr(rev) == "<Rev type='KNOWS' properties={'since': 1999}>"

    def test_rev_repr(self):
        alice = Node("Person", name="Alice")
        bob = Node("Person", name="Bob")
        relationship = Relationship(alice, "KNOWS", bob)
        self.graph.create(relationship)
        rev = -relationship.rel
        if PY2:
            assert repr(rev) == ("<Rev graph=u'http://localhost:7474/db/data/' ref=u'%s' "
                                 "type=u'KNOWS' properties={}>" % rev.ref)
        else:
            assert repr(rev) == ("<Rev graph='http://localhost:7474/db/data/' ref='%s' "
                                 "type='KNOWS' properties={}>" % rev.ref)

    def test_relationship_str(self):
        alice = Node("Person", name="Alice")
        bob = Node("Person", name="Bob")
        relationship = Relationship(alice, "KNOWS", bob)
        assert str(relationship) == '(:Person {name:"Alice"})-[:KNOWS]->(:Person {name:"Bob"})'
        self.graph.create(relationship)
        assert str(relationship) == \
            '(:Person {name:"Alice"})-[r%s:KNOWS]->(:Person {name:"Bob"})' % relationship._id

    def test_rel_str(self):
        alice = Node("Person", name="Alice")
        bob = Node("Person", name="Bob")
        relationship = Relationship(alice, "KNOWS", bob)
        self.graph.create(relationship)
        rel = relationship.rel
        assert str(rel) == '-[r%s:KNOWS]->' % rel._id

    def test_unbound_rel_str(self):
        rel = Rel("KNOWS", since=1999)
        assert str(rel) == '-[:KNOWS {since:1999}]->'

    def test_rev_str(self):
        alice = Node("Person", name="Alice")
        bob = Node("Person", name="Bob")
        relationship = Relationship(alice, "KNOWS", bob)
        self.graph.create(relationship)
        rev = -relationship.rel
        assert str(rev) == '<-[r%s:KNOWS]-' % rev._id

    def test_unbound_rev_str(self):
        rev = Rev("KNOWS", since=1999)
        assert str(rev) == '<-[:KNOWS {since:1999}]-'
