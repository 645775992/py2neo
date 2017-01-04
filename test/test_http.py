#!/usr/bin/env python
# -*- encoding: utf-8 -*-

# Copyright 2011-2017, Nigel Small
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
from unittest import TestCase

from py2neo.graph import GraphService, GraphError
from py2neo.http import set_http_header, get_http_headers, WebResource

from test.util import GraphTestCase


dbms = GraphService()
supports_bolt = dbms.supports_bolt


class TestHandler(logging.Handler):

    def __init__(self, counter, level):
        super(TestHandler, self).__init__(level)
        self.counter = counter
        self.counter.responses = []

    def emit(self, record):
        if record.msg.startswith("< "):
            self.counter.responses.append(record.args)


class HTTPCounter(object):

    def __init__(self):
        self.handler = TestHandler(self, logging.INFO)
        self.logger = logging.getLogger("httpstream")
        self.logger.addHandler(self.handler)
        self.logger.setLevel(logging.DEBUG)
        self.responses = []

    def __enter__(self):
        self.reset()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.handler = None

    def reset(self):
        self.responses = []

    @property
    def response_count(self):
        return len(self.responses)


class HeaderTestCase(GraphTestCase):

    def test_can_add_and_retrieve_global_header(self):
        set_http_header("Key1", "Value1")
        headers = get_http_headers("http", "localhost", 7474)
        assert headers["Key1"] == "Value1"

    def test_can_add_and_retrieve_header_for_specific_host_port(self):
        set_http_header("Key1", "Value1", "http", "example.com", 7474)
        set_http_header("Key1", "Value2", "http", "example.net", 7474)
        headers = get_http_headers("http", "example.com", 7474)
        assert headers["Key1"] == "Value1"

    def test_can_add_and_retrieve_multiple_headers_for_specific_host_port(self):
        set_http_header("Key1", "Value1", "http", "example.com", 7474)
        set_http_header("Key2", "Value2", "http", "example.com", 7474)
        headers = get_http_headers("http", "example.com", 7474)
        assert headers["Key1"] == "Value1"
        assert headers["Key2"] == "Value2"


class ClientErrorTestCase(GraphTestCase):

    def test_can_handle_400(self):
        resource = WebResource("http://localhost:7474/db/data/cypher")
        try:
            resource.post({}, expected=(201,))
        except GraphError as error:
            try:
                self.assert_error(
                    error, (GraphError,), "org.neo4j.server.rest.repr.BadInputException")
            except AssertionError:
                self.assert_error(
                    error, (GraphError,), "org.neo4j.server.rest.repr.InvalidArgumentsException")
        else:
            assert False

    def test_can_handle_404(self):
        node_id = self.get_non_existent_node_id()
        resource = WebResource("http://localhost:7474/db/data/node/%s" % node_id)
        try:
            resource.get_json(force=True)
        except GraphError as error:
            self.assert_error(
                error, (GraphError,), "org.neo4j.server.rest.web.NodeNotFoundException")
        else:
            assert False


class ServerErrorTestCase(GraphTestCase):

    def setUp(self):
        self.non_existent_resource = WebResource("http://localhost:7474/db/data/x")

    def test_can_handle_json_error_from_get(self):
        try:
            self.non_existent_resource.get_json(force=True)
        except GraphError as error:
            assert error.http_status_code == 404
        else:
            assert False

    def test_can_handle_json_error_from_post(self):
        try:
            self.non_existent_resource.post({}, expected=(201,)).close()
        except GraphError as error:
            assert error.http_status_code == 404
        else:
            assert False

    def test_can_handle_json_error_from_delete(self):
        try:
            self.non_existent_resource.delete(expected=(204,)).close()
        except GraphError as error:
            assert error.http_status_code == 404
        else:
            assert False


class ResourceTestCase(TestCase):

    def test_similar_resources_should_be_equal(self):
        r1 = WebResource("http://localhost:7474/db/data/node/1")
        r2 = WebResource("http://localhost:7474/db/data/node/1")
        assert r1 == r2

    def test_different_resources_should_be_unequal(self):
        r1 = WebResource("http://localhost:7474/db/data/node/1")
        r2 = WebResource("http://localhost:7474/db/data/node/2")
        assert r1 != r2
