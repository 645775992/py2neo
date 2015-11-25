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


from py2neo import Graph, Node, NodePointer, Rel, Relationship
from test.util import Py2neoTestCase


def assert_node(node, *labels, **properties):
    assert isinstance(node, Node)
    assert node.labels() == set(labels)
    assert dict(node) == properties


class CastTestCase(Py2neoTestCase):

    def test_graph_cast(self):
        assert self.graph.cast(None) is None

    def test_node_cast(self):
        alice = Node("Person", "Employee", name="Alice", age=33)
        assert_node(Node.cast())
        assert Node.cast(None) is None
        assert Node.cast(alice) is alice
        assert_node(Node.cast("Person"), "Person")
        assert_node(Node.cast(name="Alice"), name="Alice")
        assert_node(Node.cast("Person", "Employee", name="Alice", age=33),
                    "Person", "Employee", name="Alice", age=33)
        assert_node(Node.cast({"name": "Alice"}), name="Alice")
        assert_node(Node.cast(("Person", "Employee", {"name": "Alice", "age": 33})),
                    "Person", "Employee", name="Alice", age=33)
        assert Node.cast(42) == NodePointer(42)
        assert Node.cast(NodePointer(42)) == NodePointer(42)
        with self.assertRaises(TypeError):
            Node.cast(3.14)

    def test_rel_cast(self):
        knows = Rel("KNOWS", since=1999)
        assert Rel.cast() == Rel()
        assert Rel.cast(None) is None
        assert Rel.cast(knows) is knows
        assert Rel.cast("KNOWS") == Rel("KNOWS")
        assert Rel.cast(since=1999) == Rel(since=1999)
        assert Rel.cast("KNOWS", since=1999) == Rel("KNOWS", since=1999)
        assert Rel.cast({"since": 1999}) == Rel(since=1999)
        assert Rel.cast(("KNOWS", {"since": 1999})) == knows
        assert Rel.cast(Relationship({}, "KNOWS", {})) == Rel("KNOWS")

    def test_can_cast_node(self):
        alice, = self.graph.create({"name": "Alice"})
        casted = Graph.cast(alice)
        assert isinstance(casted, Node)
        assert casted.bound
        assert casted["name"] == "Alice"

    def test_can_cast_dict(self):
        casted = Graph.cast({"name": "Alice"})
        assert isinstance(casted, Node)
        assert not casted.bound
        assert casted["name"] == "Alice"

    def test_can_cast_rel(self):
        a, b, ab = self.graph.create({}, {}, (0, "KNOWS", 1))
        casted = Graph.cast(ab)
        assert isinstance(casted, Relationship)
        assert casted.bound
        assert casted.start_node() == a
        assert casted.type() == "KNOWS"
        assert casted.end_node() == b

    def test_can_cast_3_tuple(self):
        alice = Node()
        bob = Node()
        casted = Graph.cast((alice, "KNOWS", bob))
        assert isinstance(casted, Relationship)
        assert not casted.bound
        assert casted.start_node() is alice
        assert casted.type() == "KNOWS"
        assert casted.end_node() is bob

    def test_can_cast_4_tuple(self):
        alice = Node()
        bob = Node()
        casted = Graph.cast((alice, "KNOWS", bob, {"since": 1999}))
        assert isinstance(casted, Relationship)
        assert not casted.bound
        assert casted.start_node() is alice
        assert casted.type() == "KNOWS"
        assert casted.end_node() is bob
        assert casted["since"] == 1999
    
    
class RelCastTestCase(Py2neoTestCase):
    
    def test_can_cast_rel(self):
        a, b, ab = self.graph.create({}, {}, (0, "KNOWS", 1))
        casted = Relationship.cast(ab)
        assert isinstance(casted, Relationship)
        assert casted.bound
        assert casted.start_node() == a
        assert casted.type() == "KNOWS"
        assert casted.end_node() == b
        
    def test_cannot_cast_0_tuple(self):
        with self.assertRaises(TypeError):
            Relationship.cast(())

    def test_cannot_cast_1_tuple(self):
        with self.assertRaises(TypeError):
            Relationship.cast(("Alice",))

    def test_cannot_cast_2_tuple(self):
        with self.assertRaises(TypeError):
            Relationship.cast(("Alice", "KNOWS"))

    def test_can_cast_3_tuple(self):
        alice = Node()
        bob = Node()
        casted = Relationship.cast((alice, "KNOWS", bob))
        assert isinstance(casted, Relationship)
        assert not casted.bound
        assert casted.start_node() == alice
        assert casted.type() == "KNOWS"
        assert casted.end_node() == bob
        
    def test_can_cast_3_tuple_with_unbound_rel(self):
        alice = Node()
        bob = Node()
        casted = Relationship.cast((alice, ("KNOWS", {"since": 1999}), bob))
        assert isinstance(casted, Relationship)
        assert not casted.bound
        assert casted.start_node() == alice
        assert casted.type() == "KNOWS"
        assert casted.end_node() == bob
        assert casted["since"] == 1999
        
    def test_can_cast_4_tuple(self):
        alice = Node()
        bob = Node()
        casted = Relationship.cast((alice, "KNOWS", bob, {"since": 1999}))
        assert isinstance(casted, Relationship)
        assert not casted.bound
        assert casted.start_node() == alice
        assert casted.type() == "KNOWS"
        assert casted.end_node() == bob
        assert casted["since"] == 1999
        
    def test_cannot_cast_6_tuple(self):
        with self.assertRaises(TypeError):
            Relationship.cast(("Alice", "KNOWS", "Bob", "foo", "bar", "baz"))

    def test_cannot_cast_0_args(self):
        with self.assertRaises(TypeError):
            Relationship.cast()

    def test_cannot_cast_1_arg(self):
        with self.assertRaises(TypeError):
            Relationship.cast("Alice")

    def test_cannot_cast_2_args(self):
        with self.assertRaises(TypeError):
            Relationship.cast("Alice", "KNOWS")

    def test_can_cast_3_args(self):
        alice = Node()
        bob = Node()
        casted = Relationship.cast(alice, "KNOWS", bob)
        assert isinstance(casted, Relationship)
        assert not casted.bound
        assert casted.start_node() == alice
        assert casted.type() == "KNOWS"
        assert casted.end_node() == bob
        
    def test_can_cast_3_args_with_mid_tuple(self):
        alice = Node()
        bob = Node()
        casted = Relationship.cast(alice, ("KNOWS", {"since": 1999}), bob)
        assert isinstance(casted, Relationship)
        assert not casted.bound
        assert casted.start_node() == alice
        assert casted.type() == "KNOWS"
        assert casted.end_node() == bob
        assert casted["since"] == 1999
        
    def test_can_cast_3_args_with_mid_tuple_and_props(self):
        alice = Node()
        bob = Node()
        casted = Relationship.cast(alice, ("KNOWS", {"since": 1999}), bob, foo="bar")
        assert isinstance(casted, Relationship)
        assert not casted.bound
        assert casted.start_node() == alice
        assert casted.type() == "KNOWS"
        assert casted.end_node() == bob
        assert casted["since"] == 1999
        assert casted["foo"] == "bar"
        
    def test_can_cast_kwargs(self):
        alice = Node()
        bob = Node()
        casted = Relationship.cast(alice, "KNOWS", bob, since=1999)
        assert isinstance(casted, Relationship)
        assert not casted.bound
        assert casted.start_node() == alice
        assert casted.type() == "KNOWS"
        assert casted.end_node() == bob
        assert casted["since"] == 1999
        
    def test_can_cast_4_args(self):
        alice = Node()
        bob = Node()
        casted = Relationship.cast(alice, "KNOWS", bob, {"since": 1999})
        assert isinstance(casted, Relationship)
        assert not casted.bound
        assert casted.start_node() == alice
        assert casted.type() == "KNOWS"
        assert casted.end_node() == bob
        assert casted["since"] == 1999

    def test_can_cast_4_args_and_props(self):
        alice = Node()
        bob = Node()
        casted = Relationship.cast(alice, "KNOWS", bob, {"since": 1999}, foo="bar")
        assert isinstance(casted, Relationship)
        assert not casted.bound
        assert casted.start_node() == alice
        assert casted.type() == "KNOWS"
        assert casted.end_node() == bob
        assert casted["since"] == 1999
        assert casted["foo"] == "bar"
