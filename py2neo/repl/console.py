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


import atexit
from code import InteractiveConsole
import readline
import os.path
from sys import stderr

from py2neo.cypher.lang import keywords
from py2neo.graph import Graph


DEFAULT_BANNER = "Py2neo Console\n"
DEFAULT_EXIT_MESSAGE = "Tschüß!"
DEFAULT_HISTORY_FILE = os.path.expanduser("~/.py2neo_history")


class SimpleCompleter(object):

    matches = None

    def __init__(self, options):
        self.keywords = sorted(options)
        return

    def complete(self, text, state):
        if state == 0:
            # This is the first time for this text, so build a match list.
            if text:
                self.matches = [keyword
                                for keyword in self.keywords
                                if keyword and keyword.startswith(text.upper())]
            else:
                self.matches = self.keywords[:]

        # Return the state'th item from the match list,
        # if we have that many.
        try:
            response = self.matches[state] + " "
        except IndexError:
            response = None
        return response


class Console(InteractiveConsole):

    def __init__(self, hist_file=DEFAULT_HISTORY_FILE):
        InteractiveConsole.__init__(self)
        self.init_history(hist_file)
        self.graph = Graph(password="password")
        readline.set_completer(SimpleCompleter(keywords).complete)

    def init_history(self, history_file):
        readline.parse_and_bind("tab: complete")
        if hasattr(readline, "read_history_file"):
            try:
                readline.read_history_file(history_file)
            except IOError:
                pass

            def save_history():
                readline.set_history_length(1000)
                readline.write_history_file(history_file)

            atexit.register(save_history)

    def interact(self, banner=None):
        InteractiveConsole.interact(self, banner or DEFAULT_BANNER)

    def push(self, line):
        self.graph.run(line).dump(stderr)
        stderr.write("\n")
        return 0
