#!/usr/bin/env python
# -*- encoding: utf-8 -*-

# Copyright 2011-2018, Nigel Small
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


from neobolt.exceptions import ConstraintError

from py2neo import Node, GraphError
from py2neo.testing import IntegrationTestCase


class GraphSchemaTestCase(IntegrationTestCase):

    def setUp(self):
        self.reset()

    def test_can_get_all_node_labels(self):
        types = self.schema.node_labels
        assert isinstance(types, frozenset)

    def test_can_get_all_relationship_types(self):
        types = self.schema.relationship_types
        assert isinstance(types, frozenset)

    def test_schema_index(self):
        label_1 = next(self.unique_string)
        label_2 = next(self.unique_string)
        munich = Node.cast({'name': "München", 'key': "09162000"})
        self.graph.create(munich)
        munich.clear_labels()
        munich.update_labels({label_1, label_2})
        self.schema.create_index(label_1, "name")
        self.schema.create_index(label_1, "key")
        self.schema.create_index(label_2, "name")
        self.schema.create_index(label_2, "key")
        found_borough_via_name = self.node_matcher.match(label_1, name="München")
        found_borough_via_key = self.node_matcher.match(label_1, key="09162000")
        found_county_via_name = self.node_matcher.match(label_2, name="München")
        found_county_via_key = self.node_matcher.match(label_2, key="09162000")
        assert list(found_borough_via_name) == list(found_borough_via_key)
        assert list(found_county_via_name) == list(found_county_via_key)
        assert list(found_borough_via_name) == list(found_county_via_name)
        keys = self.schema.get_indexes(label_1)
        assert (u"name",) in keys
        assert (u"key",) in keys
        self.schema.drop_index(label_1, "name")
        self.schema.drop_index(label_1, "key")
        self.schema.drop_index(label_2, "name")
        self.schema.drop_index(label_2, "key")
        with self.assertRaises(GraphError):
            self.schema.drop_index(label_2, "key")
        self.graph.delete(munich)

    def test_unique_constraint(self):
        label_1 = next(self.unique_string)
        borough = Node(label_1, name="Taufkirchen")
        self.graph.create(borough)
        self.schema.create_uniqueness_constraint(label_1, "name")
        constraints = self.schema.get_uniqueness_constraints(label_1)
        assert (u"name",) in constraints
        with self.assertRaises(ConstraintError):
            self.graph.create(Node(label_1, name="Taufkirchen"))
        self.graph.delete(borough)

    def test_labels_constraints(self):
        label_1 = next(self.unique_string)
        a = Node(label_1, name="Alice")
        b = Node(label_1, name="Alice")
        self.graph.create(a | b)
        with self.assertRaises(GraphError):
            self.graph.schema.create_uniqueness_constraint(label_1, "name")
        b.remove_label(label_1)
        self.graph.push(b)
        self.schema.create_uniqueness_constraint(label_1, "name")
        a.remove_label(label_1)
        self.graph.push(a)
        b.add_label(label_1)
        self.graph.push(b)
        b.remove_label(label_1)
        self.graph.push(b)
        self.schema.drop_uniqueness_constraint(label_1, "name")
        with self.assertRaises(GraphError):
            self.schema.drop_uniqueness_constraint(label_1, "name")
        self.graph.delete(a | b)