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


from py2neo import PRODUCT
from py2neo.addressing import keyring
from py2neo.packages.httpstream import http, ClientError, ServerError
from py2neo.packages.httpstream.http import JSONResponse, user_agent
from py2neo.packages.httpstream.numbers import UNAUTHORIZED
from py2neo.status import GraphError, Unauthorized
from py2neo.util import raise_from

http.default_encoding = "UTF-8"

_http_headers = {
    (None, None, None): [
        ("User-Agent", user_agent(PRODUCT)),
        ("X-Stream", "true"),
    ],
}


def set_http_header(key, value, scheme=None, host=None, port=None):
    """ Add an HTTP header for all future requests. If a `host_port` is
    specified, this header will only be included in requests to that
    destination.

    :arg key: name of the HTTP header
    :arg value: value of the HTTP header
    :arg scheme:
    :arg host:
    :arg port:
    """
    address_key = (scheme, host, port)
    if address_key in _http_headers:
        _http_headers[address_key].append((key, value))
    else:
        _http_headers[address_key] = [(key, value)]


def get_http_headers(scheme, host, port):
    """Fetch all HTTP headers relevant to the `host_port` provided.

    :arg scheme:
    :arg host:
    :arg port:
    """
    uri_headers = {}
    for (s, h, p), headers in _http_headers.items():
        if (s is None or s == scheme) and (h is None or h == host) and (p is None or p == port):
            uri_headers.update(headers)
    for uri, auth in keyring.items():
        if auth and uri.scheme in ("http", "https") and uri.host == host and uri.port == port:
            uri_headers["Authorization"] = auth.http_authorization
    return uri_headers


class WebResource(object):
    """ Base class for all local resources mapped to remote counterparts.
    """

    def __init__(self, uri):
        from py2neo.packages.httpstream import Resource
        self.resource = Resource(uri)

    def __eq__(self, other):
        try:
            return self.uri == other.uri
        except AttributeError:
            return False

    def __ne__(self, other):
        return not self.__eq__(other)

    @property
    def uri(self):
        return self.resource.uri.string

    def request(self, method, **kwargs):
        uri = self.resource.__uri__
        headers = get_http_headers(uri.scheme, uri.host, uri.port)
        try:
            return HTTPResponse(uri.string, method(headers=headers, **kwargs))
        except (ClientError, ServerError) as error:
            return HTTPResponse(uri.string, error)

    def get(self):
        """ Perform an HTTP GET to this resource.
        """
        return self.request(self.resource.get, cache=True)

    def post(self, body=None):
        """ Perform an HTTP POST to this resource.
        """
        return self.request(self.resource.post, body=body)

    def delete(self):
        """ Perform an HTTP DELETE to this resource.
        """
        return self.request(self.resource.delete)


class HTTPResponse(object):

    def __init__(self, uri, response):
        self.uri = uri
        self.inner = response
        self.status_code = response.status_code
        if 400 <= self.status_code < 600:
            if self.status_code == UNAUTHORIZED:
                raise Unauthorized(self.uri)
            if isinstance(response, JSONResponse):
                content = dict(response.content, request=response.request, response=response)
            else:
                content = {}
            message = content.pop("message", "HTTP request returned response %s" % self.status_code)
            raise_from(GraphError(message, **content), response)

    @property
    def location(self):
        return self.inner.location

    @property
    def content(self):
        return self.inner.content

    def close(self):
        self.inner.close()
