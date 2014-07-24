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


from __future__ import unicode_literals

from py2neo import Node


def test_can_merge_on_label_only(graph):
    graph.delete(*graph.find("Person"))
    merged = list(graph.merge("Person"))
    assert len(merged) == 1
    assert isinstance(merged[0], Node)
    assert merged[0].labels == {"Person"}


def test_can_merge_on_label_and_property(graph):
    graph.delete(*graph.find("Person", "name", "Alice"))
    merged = list(graph.merge("Person", "name", "Alice"))
    assert len(merged) == 1
    assert isinstance(merged[0], Node)
    assert merged[0].labels == {"Person"}
    assert merged[0].properties == {"name": "Alice"}
