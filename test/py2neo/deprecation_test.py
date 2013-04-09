##/usr/bin/env python
## -*- coding: utf-8 -*-
#
## Copyright 2011-2013, Nigel Small
##
## Licensed under the Apache License, Version 2.0 (the "License");
## you may not use this file except in compliance with the License.
## You may obtain a copy of the License at
##
##     http://www.apache.org/licenses/LICENSE-2.0
##
## Unless required by applicable law or agreed to in writing, software
## distributed under the License is distributed on an "AS IS" BASIS,
## WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
## See the License for the specific language governing permissions and
## limitations under the License.
#
#from py2neo import neo4j
#import unittest
#
#
#class DeprecationTest(unittest.TestCase):
#
#    def setUp(self):
#        self.graph_db = neo4j.GraphDatabaseService()
#        self.graph_db.clear()
#        self.alice, self.bob = self.graph_db.create(
#            {"name": "Alice"},
#            {"name": "Bob"},
#        )
#
#    def test_get_or_create_relationships(self):
#        self.assertWarns(DeprecationWarning, self.graph_db.get_or_create_relationships)
#
#    def test_create_relationship_from(self):
#        self.assertWarns(DeprecationWarning, self.alice.create_relationship_from, self.bob, "KNOWS")
#
#    def test_create_relationship_to(self):
#        self.assertWarns(DeprecationWarning, self.alice.create_relationship_to, self.bob, "KNOWS")
#
#    def test_get_related_nodes(self):
#        self.assertWarns(DeprecationWarning, self.alice.get_related_nodes)
#
#    def test_get_relationships(self):
#        self.assertWarns(DeprecationWarning, self.alice.get_relationships)
#
#    def test_get_relationships_with(self):
#        self.assertWarns(DeprecationWarning, self.alice.get_relationships_with, self.bob)
#
#    def test_get_single_related_node(self):
#        self.assertWarns(DeprecationWarning, self.alice.get_single_related_node)
#
#    def test_get_single_relationship(self):
#        self.assertWarns(DeprecationWarning, self.alice.get_single_relationship)
#
#    def test_has_relationship(self):
#        self.assertWarns(DeprecationWarning, self.alice.has_relationship)
#
#    def test_has_relationship_with(self):
#        self.assertWarns(DeprecationWarning, self.alice.has_relationship_with, self.bob)
#
#    def test_is_related_to(self):
#        self.assertWarns(DeprecationWarning, self.alice.is_related_to, self.bob)
#
#
#class BatchDeprecationTest(unittest.TestCase):
#
#    def setUp(self):
#        self.graph_db = neo4j.GraphDatabaseService()
#        self.graph_db.clear()
#        self.batch = neo4j.WriteBatch(self.graph_db)
#
#    def test_create_node(self):
#        self.assertWarns(DeprecationWarning, self.batch.create_node, {})
#
#    def test_create_relationship(self):
#        self.assertWarns(DeprecationWarning, self.batch.create_relationship, 0, "KNOWS", 1)
#
#    def test_delete_node(self):
#        self.batch.create({"name": "Alice"})
#        alice, = self.batch.submit()
#        self.assertWarns(DeprecationWarning, self.batch.delete_node, alice)
#
#    def test_delete_relationship(self):
#        self.batch.create({"name": "Alice"})
#        self.batch.create({"name": "Bob"})
#        self.batch.create((0, "KNOWS", 1))
#        alice, bob, ab = self.batch.submit()
#        self.assertWarns(DeprecationWarning, self.batch.delete_relationship, ab)
#
#
#if __name__ == '__main__':
#    unittest.main()
