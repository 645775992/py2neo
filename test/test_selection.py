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


from os.path import join as path_join, dirname
from py2neo import Node, NodeSelector
from test.util import GraphTestCase


class NodeFinderTestCase(GraphTestCase):

    @classmethod
    def setUpClass(cls):
        cls.graph.delete_all()
        with open(path_join(dirname(__file__), "..", "resources", "movies.cypher")) as f:
            cypher = f.read()
        cls.graph.run(cypher)

    @classmethod
    def tearDownClass(cls):
        cls.graph.delete_all()

    def setUp(self):
        self.selector = NodeSelector(self.graph)

    def test_can_select_by_label_key_value(self):
        found = list(self.selector.select("Person", name="Keanu Reeves"))
        assert len(found) == 1
        first = found[0]
        assert isinstance(first, Node)
        assert first["name"] == "Keanu Reeves"
        assert first["born"] == 1964

    def test_can_select_by_label_only(self):
        found = list(self.selector.select("Person"))
        assert len(found) == 131

    def test_can_select_all_nodes(self):
        found = list(self.selector.select())
        assert len(found) == 169

    def test_can_select_by_label_and_multiple_values(self):
        found = list(self.selector.select("Person", name="Keanu Reeves", born=1964))
        assert len(found) == 1
        first = found[0]
        assert isinstance(first, Node)
        assert first["name"] == "Keanu Reeves"
        assert first["born"] == 1964

    def test_multiple_values_must_intersect(self):
        found = list(self.selector.select("Person", name="Keanu Reeves", born=1963))
        assert len(found) == 0

    def test_custom_conditions(self):
        found = list(self.selector.select("Person").where("_.name =~ 'K.*'"))
        found_names = {actor["name"] for actor in found}
        assert found_names == {'Keanu Reeves', 'Kelly McGillis', 'Kevin Bacon',
                               'Kevin Pollak', 'Kiefer Sutherland', 'Kelly Preston'}

    def test_multiple_custom_conditions(self):
        found = list(self.selector.select("Person").where("_.name =~ 'J.*'", "_.born >= 1960", "_.born < 1970"))
        found_names = {actor["name"] for actor in found}
        assert found_names == {'James Marshall', 'John Cusack', 'John Goodman', 'John C. Reilly', 'Julia Roberts'}

    def test_limit(self):
        found = list(self.selector.select("Person").where("_.name =~ 'K.*'").limit(3))
        assert len(found) == 3
        for actor in found:
            assert actor["name"] in {'Keanu Reeves', 'Kelly McGillis', 'Kevin Bacon',
                                     'Kevin Pollak', 'Kiefer Sutherland', 'Kelly Preston'}
