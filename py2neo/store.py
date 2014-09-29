#!/usr/bin/env python
# -*- encoding: utf-8 -*-

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


import os
from shutil import copytree, rmtree


class GraphStore(object):

    # TODO: instances

    @classmethod
    def for_server(cls, server):
        # TODO: actually sniff config files for the true path
        return GraphStore(os.path.join(server.home, "data", "graph.db"))

    def __init__(self, path):
        self.path = path

    @property
    def locked(self):
        return os.path.isfile(os.path.join(self.path, "lock"))

    def drop(self, force=False):
        if force or not self.locked:
            rmtree(self.path, ignore_errors=force)
        else:
            raise RuntimeError("Refusing to drop database store while in use")

    def load(self, path, force=False):
        if force or not self.locked:
            if os.path.isfile(path):
                # unzip to temporary dir
                # change path to point to temporary dir
                pass
            rmtree(self.path, ignore_errors=force)
            copytree(path, self.path)
        else:
            raise RuntimeError("Refusing to load database store while in use")

    def save(self, path, force=False):
        if force or not self.locked:
            copytree(self.path, path)
        else:
            raise RuntimeError("Refusing to save database store while in use")
