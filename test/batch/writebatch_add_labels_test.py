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

from py2neo import Graph, WriteBatch


@pytest.skip(not Graph().supports_node_labels)
def test_can_add_labels_to_preexisting_node(graph):
    alice, = graph.create({"name": "Alice"})
    batch = WriteBatch(graph)
    batch.add_labels(alice, "human", "female")
    batch.run()
    assert alice.get_labels() == {"human", "female"}


@pytest.skip(not Graph().supports_node_labels)
def test_can_add_labels_to_node_in_same_batch(graph):
    batch = WriteBatch(graph)
    a = batch.create({"name": "Alice"})
    batch.add_labels(a, "human", "female")
    results = batch.submit()
    alice = results[batch.find(a)]
    assert alice.get_labels() == {"human", "female"}
