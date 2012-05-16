#!/usr/bin/env python

# Copyright 2011 Nigel Small
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

"""The neo4j module provides the main Neo4j client functionality within py2neo.
This module will be the starting point for most people.
"""

__author__    = "Nigel Small <py2neo@nigelsmall.org>"
__copyright__ = "Copyright 2011 Nigel Small"
__license__   = "Apache License, Version 2.0"


try:
    from urllib.parse import quote
except ImportError:
    from urllib import quote
try:
    from . import rest, batch, cypher
except ImportError:
    import rest, batch, cypher
except ValueError:
    import rest, batch, cypher

import logging
logger = logging.getLogger(__name__)

import warnings


DEFAULT_URI = "http://localhost:7474/db/data/"

def _flatten(*args, **kwargs):
    """Flatten all supplied positional and keyword arguments into a single
    dictionary, dropping all keys with a leading underscore.
    """
    data = {}
    for arg in args:
        try:
            data.update(dict([
                (arg.__class__.__name__ + "." + key, value)
                for key, value in arg.__dict__.items()
            ]))
        except AttributeError:
            data.update(arg)
    data.update(kwargs)
    # remove any properties beginning with an underscore
    data = dict([
        (key, value)
        for key, value in data.items()
        if not key.startswith("_")
    ])
    return data

def _numberise(n):
    """Convert a value to an integer if possible, simply returning the input
    value itself if not.
    """
    try:
        return int(n)
    except ValueError:
        return n

def _quote(string, safe='/'):
    try:
        return quote(string, safe)
    except Exception:
        return string


class Direction(object):
    """Used to define the direction of a relationship.
    """

    BOTH     = 'all'
    INCOMING = 'incoming'
    OUTGOING = 'outgoing'


class GraphDatabaseService(rest.Resource):
    """An instance of a `Neo4j <http://neo4j.org/>`_ database identified by its
    base URI. Generally speaking, this is the only URI which a system
    attaching to this service should need to be aware of; all further entity
    URIs will be discovered automatically from within response content
    (see `Hypermedia <http://en.wikipedia.org/wiki/Hypermedia>`_).

    :param uri:       the base URI of the database (defaults to <http://localhost:7474/db/data/>)
    :param metadata:  optional resource metadata

    The following code illustrates how to attach to a database server and
    display its version number:

        >>> from py2neo import rest, neo4j
        >>> uri = "http://localhost:7474/db/data/"
        >>> try:
        >>>     graph_db = neo4j.GraphDatabaseService(uri)
        >>>     print graph_db.neo4j_version
        >>> except rest.NoResponse:
        >>>     print "Cannot connect to host"
        >>> except rest.ResourceNotFound:
        >>>     print "Database service not found"

    """

    def __init__(self, uri=None, metadata=None, **kwargs):
        uri = uri or DEFAULT_URI
        rest.Resource.__init__(self, uri, metadata=metadata, **kwargs)
        if self._uri.endswith("/"):
            self._base_uri, self._relative_uri = self._uri.rpartition("/")[0:2]
        else:
            self._base_uri, self._relative_uri = self._uri, "/"
        self._extensions = self._lookup('extensions')
        if 'neo4j_version' in self._metadata:
            # must be version 1.5 or greater
            self._neo4j_version = self._lookup('neo4j_version')
            self._batch_uri = self._lookup('batch')
        else:
            # assume version 1.4
            self._neo4j_version = "1.4"
            self._batch_uri = self._base_uri + "/batch"
        if 'cypher' in self._metadata:
            self._cypher_uri = self._lookup('cypher')
        else:
            try:
                self._cypher_uri = self._extension_uri('CypherPlugin', 'execute_query')
            except NotImplementedError:
                self._cypher_uri = None
        try:
            self._geoff_uri = self._extension_uri('GeoffPlugin', 'load_from_string')
        except NotImplementedError:
            self._geoff_uri = None
        try:
            self._gremlin_uri = self._extension_uri('GremlinPlugin', 'execute_script')
        except NotImplementedError:
            self._gremlin_uri = None
        self._neo4j_version = tuple(map(_numberise, self._neo4j_version.replace("-", ".").split(".")))
        self._node_indexes = {}
        self._relationship_indexes = {}

    def _execute(self, plugin_name, function_name, data):
        """Execute a POST request against the specified plugin function using
        the supplied data; returns the value from the response.

        :param plugin_name: the name of the plugin to call
        :param function_name: the name of the function to call within the specified plugin
        :param data: the data to pass to the function call
        :raise NotImplementedError: when the specified plugin or function is not available
        :return: the data returned from the function call

        """
        function_uri = self._extension_uri(plugin_name, function_name)
        return self._post(function_uri, data)

    def _extension_uri(self, plugin_name, function_name):
        """Return the URI of an extension function.

        :param plugin_name: the name of the plugin
        :param function_name: the name of the function within the specified plugin
        :raise NotImplementedError: when the specified plugin or function is not available
        :return: the data returned from the function call
        """
        if plugin_name not in self._extensions:
            raise NotImplementedError(plugin_name)
        plugin = self._extensions[plugin_name]
        if function_name not in plugin:
            raise NotImplementedError(plugin_name + "." + function_name)
        return self._extensions[plugin_name][function_name]

    def create(self, *entities):
        """Create and return multiple nodes and/or relationships as part of a
        single batch. For a node, simply pass a dictionary of properties; for a
        relationship, pass a tuple of (start, type, end) or (start, type, end,
        data) where start and end may be Node instances or zero-based integral
        references to other node entities within this batch.
        """
        try:
            return map(batch.result, self._post(self._batch_uri, [
                batch.creator(i, entities[i])
                for i in range(len(entities))
            ]))
        except SystemError as err:
            raise batch.BatchError(*err.args)

    def create_node(self, *props, **kwprops):
        """Create and return a new node, optionally with properties.
        """
        return Node(self._post(self._lookup('node'), _flatten(*props, **kwprops)))

    def create_nodes(self, *props):
        """Create a number of new nodes for all supplied properties as part of
        a single batch; returns a list of all new nodes.
        """
        warnings.warn("GraphDatabaseService.create_nodes is deprecated; "
                      "please use 'create' method instead")
        return [
            Node(result['location'], metadata=result['body'])
            for result in self._post(self._batch_uri, [
                {
                    'method': 'POST',
                    'to': "".join(self._lookup('node').rpartition("/node")[1:3]),
                    'body': _flatten(props[i]),
                    'id': i
                }
                for i in range(len(props))
            ])
        ]

    def create_node_index(self, name, config=None):
        """Create and return a new node index with the supplied name and
        configuration.
        """
        index = Index(Node, uri=self._post(self._lookup('node_index'), {
            'name': name,
            'config': config or {}
        }))
        self._node_indexes.update({name: index})
        return index

    def create_relationships(self, *descriptors):
        """Create new relationships based on the supplied descriptors as
        part of a single batch. Each descriptor should be a dictionary
        consisting of two nodes, named ``start_node`` and ``end_node``,
        a ``type`` and optionally ``data`` to be attached to the relationship,
        for example:

            >>> gdb.create_relationships({
            ...     "start_node": node1,
            ...     "end_node": node2,
            ...     "type": "KNOWS"
            ... }, {
            ...     "start_node": node2,
            ...     "end_node": node3,
            ...     "type": "LIKES",
            ...     "data": {"amount": "lots"}
            ... })
        """
        warnings.warn("GraphDatabaseService.create_relationships is "
                      "deprecated; please use 'create' method instead")
        return [
            Relationship(result['body']['self'], metadata=result['body'])
            for result in self._post(self._batch_uri, [
                {
                    'method': 'POST',
                    'to': "".join(descriptors[i]['start_node']._lookup('create_relationship').rpartition("/node")[1:3]),
                    'body': {
                        'to': descriptors[i]['end_node']._uri,
                        'type': descriptors[i]['type'],
                        'data': _flatten(descriptors[i]['data']) if 'data' in descriptors[i] else None
                    },
                    'id': i
                }
                for i in range(len(descriptors))
            ])
        ]

    def create_relationship_index(self, name, config=None):
        """Create and return a new relationship index with the supplied name
        and configuration.
        """
        index = Index(Relationship, uri=self._post(self._lookup('relationship_index'), {
            'name': name,
            'config': config or {}
        }))
        self._relationship_indexes.update({name: index})
        return index

    def delete(self, *entities):
        """Delete multiple nodes and/or relationships as part of a single
        batch.
        """
        self._post(self._batch_uri, [
            {
                'method': 'DELETE',
                'to': entities[i]._relative_uri,
                'id': i
            }
            for i in range(len(entities))
        ])

    def get_node(self, id):
        """Fetch a node by its ID.
        """
        return Node(self._lookup('node') + "/" + str(id))

#    # TODO
#    def get_nodes(self, <match criteria>): ...

    def get_node_count(self):
        """Fetch the number of nodes in this graph as an integer.
        """
        data, metadata = cypher.execute(self, "start z=node(*) return count(z)")
        if data and data[0]:
            return data[0][0]
        else:
            return 0

    def get_node_index(self, name):
        """Fetch a specifically named node index from the current graph. If
        such an index does not exist, one is created with default
        configuration.
        """
        if name not in self._node_indexes:
            self.get_node_indexes()
        if name in self._node_indexes:
            return self._node_indexes[name]
        else:
            return self.create_node_index(name)

    def get_node_indexes(self):
        """Fetch a dictionary of all available node indexes within this
        database instance.
        """
        indexes = self._get(self._lookup('node_index')) or {}
        self._node_indexes = dict([
            (index, Index(Node, template_uri=indexes[index]['template']))
            for index in indexes
        ])
        return self._node_indexes

    def get_properties(self, *entities):
        """Fetch properties for multiple nodes and/or relationships as part
        of a single batch; returns a list of dictionaries in the same order
        as the supplied entities.
        """
        return [
            result['body']['data']
            for result in self._post(self._batch_uri, [
                {
                    'method': 'GET',
                    'to': entities[i]._relative_uri,
                    'id': i
                }
                for i in range(len(entities))
            ])
        ]

    def get_relationship(self, id):
        """Fetch a relationship by its ID.
        """
        return Relationship(self._lookup('relationship') + "/" + str(id))

#    # TODO
#    def get_relationships(self, start_node=None, type=None, end_node=None):
#        type = type or ""
#        if type:
#            type = ":" + type
#        data, metadata = cypher.execute(self,
#            "start a=node({A}) match a-[r" + type + "]->b return r",
#            {"A": start_node.id}
#        )
#        return [row[0] for row in data]

    def get_relationship_index(self, name):
        """Fetch a specifically named relationship index from the current
        graph. If such an index does not exist, one is created with default
        configuration.
        """
        if name not in self._relationship_indexes:
            self.get_relationship_indexes()
        if name in self._relationship_indexes:
            return self._relationship_indexes[name]
        else:
            return self.create_relationship_index(name)

    def get_relationship_indexes(self):
        """Fetch a dictionary of all available relationship indexes within this
        database instance.
        """
        indexes = self._get(self._lookup('relationship_index')) or {}
        self._relationship_indexes = dict([
            (index, Index(Relationship,
                template_uri=indexes[index]['template']
            ))
            for index in indexes
        ])
        return self._relationship_indexes

    def get_relationship_types(self):
        """Fetch a list of relationship type names currently defined within
        this database instance.
        """
        return self._get(self._lookup('relationship_types'))

    def get_reference_node(self):
        """Fetch the reference node for the current graph.
        """
        return Node(self._lookup('reference_node'))

    def get_subreference_node(self, name):
        """Fetch a named subreference node from the current graph. If such a
        node does not exist, one is created.
        """
        ref_node = self.get_reference_node()
        subreference_node = ref_node.get_single_related_node(Direction.OUTGOING, name)
        if subreference_node is None:
            subreference_node = self.create_node()
            ref_node.create_relationship_to(subreference_node, name)
        return subreference_node

    @property
    def neo4j_version(self):
        """Return the database software version as a tuple.
        """
        return self._neo4j_version


class _Indexable(object):
    """Mixin class used by indexable entities.
    """

    def __init__(self, index_entry_uri=None, index_uri=None):
        self._index_entry_uri = index_entry_uri
        if self._index_entry_uri is None:
            self._relative_index_entry_uri = None
        else:
            self._relative_index_entry_uri = "".join(self._index_entry_uri.partition("/index")[1:])
        self._index_uri = index_uri

    def __eq__(self, other):
        return self._index_entry_uri == other._index_entry_uri

    def __ne__(self, other):
        return self._index_entry_uri != other._index_entry_uri


class _PropertyContainer(rest.Resource):
    """Base class from which node and relationship classes inherit. Extends a
    :py:class:`py2neo.rest.Resource` by providing property management
    functionality.
    """

    def __init__(self, uri, metadata=None, max_age=0, **kwargs):
        """Create a representation of an indexable resource (node or
        relationship) identified by URI; optionally accepts further URIs
        representing both an index for this resource type plus the specific
        entry within that index.

        :param uri:             the URI identifying this resource
        :param metadata:        an index of RESTful URIs
        """
        rest.Resource.__init__(self, uri, metadata=metadata, **kwargs)
        if metadata and "data" in metadata:
            self._properties = rest.PropertyCache(metadata["data"], max_age=max_age)
        else:
            self._properties = rest.PropertyCache(max_age=max_age)

    def __pull(self):
        self._properties.update(self._get(self._lookup('properties')))

    def __getitem__(self, key):
        """Return a named property for this resource.
        """
        if self._properties.needs_update:
            self.__pull()
        return self._properties[key]

    def __setitem__(self, key, value):
        """Set a named property for this resource to the supplied value.
        """
        self._put(self._lookup('property').format(key=key), value)

    def __delitem__(self, key):
        """Delete a named property for this resource.
        """
        self._delete(self._lookup('property').format(key=key))

    def __contains__(self, key):
        if self._properties.needs_update:
            self.__pull()
        return key in self._properties

    def get_properties(self):
        """Return all properties for this resource.
        """
        if self._properties.needs_update:
            self.__pull()
        return self._properties.get_all()

    def set_properties(self, *args, **kwargs):
        """Set all properties for this resource to the supplied values.
        """
        p = _flatten(*args, **kwargs)
        self._put(self._lookup('properties'), p)
        self._properties.update(p)

    def remove_properties(self):
        """Delete all properties for this resource.
        """
        self._delete(self._lookup('properties'))


class Node(_Indexable, _PropertyContainer):
    """A node within a graph, identified by a URI. This class is
    :py:class:`_Indexable` and, as such, may also contain URIs identifying how
    this relationship is represented within an index.
    
    :param uri:             the URI identifying this node
    :param index_entry_uri: the URI of the entry in an index pointing to this node
    :param index_uri:       the URI of the index containing the above node entry
    :param metadata:        an index of RESTful URIs
    """

    def __init__(self, uri, index_entry_uri=None, index_uri=None, metadata=None, **kwargs):
        _Indexable.__init__(self, index_entry_uri=index_entry_uri, index_uri=index_uri)
        _PropertyContainer.__init__(self, uri, metadata=metadata, **kwargs)
        self._relative_uri = "".join(self._uri.rpartition("/node")[1:])
        self._id = int('0' + uri.rpartition('/')[-1])
        self._graph_db = GraphDatabaseService(self._uri.rpartition("/node")[0] + "/")

    def __repr__(self):
        return '{0}({1})'.format(
            self.__class__.__name__,
            repr(self._uri if self._index_entry_uri is None else self._index_entry_uri)
        )

    def __str__(self):
        """Return a human-readable string representation of this node
        object, e.g.:
        
            >>> print str(my_node)
            '(42)'
        """
        return "({0})".format(self._id)

    def __eq__(self, other):
        """Determine equality of this node with another node.
        """
        return rest.Resource.__eq__(self, other) and _Indexable.__eq__(self, other)

    def __ne__(self, other):
        """Determine inequality of this node with another node.
        """
        return rest.Resource.__ne__(self, other) or _Indexable.__ne__(self, other)

    @property
    def id(self):
        """Return the unique id for this node.
        """
        return self._id

    def get_id(self):
        """Return the unique id for this node.
        """
        warnings.warn("Node.get_id is deprecated; please use 'id' property "
                      "instead")
        return self.id

    def create_relationship_to(self, other_node, type, *args, **kwargs):
        """Create and return a new relationship of type `type` from the node
        represented by the current instance to the node represented by
        `other_node`.
        """
        return Relationship(self._post(self._lookup('create_relationship'), {
            'to': other_node._uri,
            'type': type,
            'data': _flatten(*args, **kwargs)
        }))

    def get_relationships(self, direction=Direction.BOTH, *types):
        """Fetch all relationships from the current node in a given
        `direction` of a specific `type` (if supplied).
        """
        if types:
            uri = self._lookup(direction + '_typed_relationships').replace('{-list|&|types}', '&'.join(types))
        else:
            uri = self._lookup(direction + '_relationships')
        return [
            Relationship(rel['self'])
            for rel in self._get(uri)
        ]

    def get_single_relationship(self, direction, type):
        """Fetch only one relationship from the current node in the given
        `direction` of the specified `type`, if any such relationships exist.
        """
        relationships = self.get_relationships(direction, type)
        return relationships[0] if len(relationships) > 0 else None

    def has_relationship(self, direction=Direction.BOTH, *types):
        """Return :py:const:`True` if this node has any relationships with the
        specified criteria, :py:const:`False` otherwise.
        """
        relationships = self.get_relationships(direction, *types)
        return len(relationships) > 0

    def get_related_nodes(self, direction=Direction.BOTH, *types):
        """
        Fetch all nodes related to the current node by a relationship in a
        given `direction` of a specific `type` (if supplied).
        """
        if types:
            uri = self._lookup(direction + '_typed_relationships').replace('{-list|&|types}', '&'.join(types))
        else:
            uri = self._lookup(direction + '_relationships')
        return [
            Node(rel['start'] if rel['end'] == self._uri else rel['end'])
            for rel in self._get(uri)
        ]

    def get_single_related_node(self, direction, type):
        """Return only one node related to the current node by a relationship
        in the given `direction` of the specified `type`, if any such
        relationships exist.
        """
        nodes = self.get_related_nodes(direction, type)
        return nodes[0] if len(nodes) > 0 else None

    def is_related_to(self, other, direction=Direction.BOTH, type=None):
        """Return :py:const:`True` if the current node is related to the other
        node using the relationship criteria supplied, :py:const:`False`
        otherwise.
        """
        if not isinstance(other, Node):
            raise ValueError
        if direction == Direction.BOTH:
            query = "start a=node({0}),b=node({1}) match a-{2}-b return count(*)"
        elif direction == Direction.OUTGOING:
            query = "start a=node({0}),b=node({1}) match a-{2}->b return count(*)"
        elif direction == Direction.INCOMING:
            query = "start a=node({0}),b=node({1}) match a<-{2}-b return count(*)"
        else:
            raise ValueError
        if type:
            type = "[:" + type + "]"
        else:
            type = ""
        query = query.format(self.id, other.id, type)
        rows, columns = cypher.execute(self._graph_db, query)
        return bool(rows)

    def get_relationships_with(self, other, direction=Direction.BOTH, type=None):
        """Return all relationships between this node and another node using
        the relationship criteria supplied.
        """
        if not isinstance(other, Node):
            raise ValueError
        if direction == Direction.BOTH:
            query = "start a=node({0}),b=node({1}) match a-{2}-b return r"
        elif direction == Direction.OUTGOING:
            query = "start a=node({0}),b=node({1}) match a-{2}->b return r"
        elif direction == Direction.INCOMING:
            query = "start a=node({0}),b=node({1}) match a<-{2}-b return r"
        else:
            raise ValueError
        if type:
            type = "[r:" + type + "]"
        else:
            type = "[r]"
        query = query.format(self.id, other.id, type)
        rows, columns = cypher.execute(self._graph_db, query)
        return [row[0] for row in rows]

    def traverse(self, order=None, uniqueness=None, relationships=None, prune=None, filter=None, max_depth=None):
        """Return a :py:class:`Traverser` instance for the current node.

            >>> t = t1.traverse(order="depth_first",
            ...                 max_depth=2,
            ...                 relationships=[("KNOWS","out"), "LOVES"],
            ...                 prune=("javascript", "position.endNode().getProperty('foo') == 'bar';")
            ... )
        """
        warnings.warn("Node.traverse is deprecated; please use Cypher queries "
                      "instead")
        td = TraversalDescription()
        if order:
            td = td.order(order)
        if uniqueness:
            td = td.uniqueness(uniqueness)
        if relationships:
            for relationship in (relationships or []):
                if isinstance(relationship, str):
                    td = td.relationships(relationship)
                else:
                    try:
                        if isinstance(relationship, unicode):
                            td = td.relationships(relationship)
                        else:
                            td = td.relationships(*relationship)
                    except NameError:
                        td = td.relationships(*relationship)
        if prune:
            td = td.prune_evaluator(prune[0], prune[1])
        if filter:
            td = td.return_filter(filter[0], filter[1])
        if max_depth:
            td = td.max_depth(max_depth)
        return td.traverse(self)

    def delete(self):
        """Delete this node from the database.
        """
        self._delete(self._lookup('self'))


class Relationship(_Indexable, _PropertyContainer):
    """A relationship within a graph, identified by a URI. This class is
    :py:class:`_Indexable` and, as such, may also contain URIs identifying how
    this relationship is represented within an index.
    
    :param uri:             the URI identifying this relationship
    :param index_entry_uri: the URI of the entry in an index pointing to this relationship
    :param index_uri:       the URI of the index containing the above relationship entry
    :param metadata:        an index of RESTful URIs
    """

    def __init__(self, uri, index_entry_uri=None, index_uri=None, metadata=None, **kwargs):
        _Indexable.__init__(self, index_entry_uri=index_entry_uri, index_uri=index_uri)
        _PropertyContainer.__init__(self, uri, metadata=metadata, **kwargs)
        self._relative_uri = "".join(self._uri.rpartition("/relationship")[1:])
        self._type = self._lookup('type')
        self._data = self._lookup('data')
        self._start_node = None
        self._end_node = None
        self._id = int('0' + uri.rpartition('/')[-1])

    def __repr__(self):
        return '{0}({1})'.format(
            self.__class__.__name__,
            repr(self._uri if self._index_entry_uri is None else self._index_entry_uri)
        )

    def __str__(self):
        """Return a human-readable string representation of this relationship
        object, e.g.:
        
            >>> print str(my_rel)
            '-[23:KNOWS]->'
        
        """
        return "-[{0}:{1}]->".format(self._id, self._type)

    def __eq__(self, other):
        """Determine equality of this relationship with another relationship.
        """
        return rest.Resource.__eq__(self, other) and _Indexable.__eq__(self, other)

    def __ne__(self, other):
        """Determine inequality of this relationship with another relationship.
        """
        return rest.Resource.__ne__(self, other) or _Indexable.__ne__(self, other)

    @property
    def id(self):
        """Return the unique id for this relationship.
        """
        return self._id

    def get_id(self):
        """Return the unique id for this relationship.
        """
        warnings.warn("Relationship.get_id is deprecated; please use 'id'"
                      "property instead")
        return self.id

    @property
    def type(self):
        """Return the type of this relationship.
        """
        return self._type

    def get_type(self):
        """Return the type of this relationship.
        """
        warnings.warn("Relationship.get_type is deprecated; please use 'type' "
                      "property instead")
        return self.type

    def is_type(self, type):
        """Return :py:const:`True` if this relationship is of the given type.
        """
        return self._type == type

    @property
    def nodes(self):
        """Return a tuple of the two nodes attached to this relationship.
        """
        return self.start_node, self.end_node

    def get_nodes(self):
        """Return a tuple of the two nodes attached to this relationship.
        """
        warnings.warn("Relationship.get_nodes is deprecated; please use "
                      "'nodes' property instead")
        return self.nodes

    @property
    def start_node(self):
        """Return the start node of this relationship.
        """
        if not self._start_node:
            self._start_node = Node(self._lookup('start'))
        return self._start_node

    def get_start_node(self):
        """Return the start node of this relationship.
        """
        warnings.warn("Relationship.get_start_node is deprecated; please use "
                      "'start_node' property instead")
        return self.start_node

    @property
    def end_node(self):
        """Return the end node of this relationship.
        """
        if not self._end_node:
            self._end_node = Node(self._lookup('end'))
        return self._end_node

    def get_end_node(self):
        """Return the end node of this relationship.
        """
        warnings.warn("Relationship.get_end_node is deprecated; please use "
                      "'end_node' property instead")
        return self.end_node

    def get_other_node(self, node):
        """Return a node object representing the node within this
        relationship which is not the one supplied.
        """
        if self._lookup('end') == node._uri:
            return self.get_start_node()
        else:
            return self.get_end_node()

    def delete(self):
        """Delete this relationship from the database.
        """
        self._delete(self._lookup('self'))


class Path(object):
    """Sequence of nodes connected by relationships.
    Note that there should always be exactly one more node supplied to
    the constructor than there are relationships.
    
    :raise ValueError: when number of nodes is not exactly one more than number of relationships
    """

    def __init__(self, nodes, relationships):
        if len(nodes) - len(relationships) == 1:
            self._nodes = nodes
            self._relationships = relationships
        else:
            raise ValueError

    def __str__(self):
        """Return a human-readable string representation of this path object,
        e.g.:
        
            >>> print str(my_path)
            '(0)-[:CUSTOMERS]->(1)-[:CUSTOMER]->(42)'
        
        """
        return "".join([
            str(self._nodes[i]) + str(self._relationships[i])
            for i in range(len(self._relationships))
        ]) + str(self._nodes[-1])

    def __len__(self):
        """Return the length of this path (equivalent to the number of
        relationships).
        """
        return len(self._relationships)

    @property
    def nodes(self):
        """Return a list of all the nodes which make up this path.
        """
        return self._nodes

    @property
    def relationships(self):
        """Return a list of all the relationships which make up this path.
        """
        return self._relationships

    @property
    def start_node(self):
        """Return the start node from this path.
        """
        return self._nodes[0]

    @property
    def end_node(self):
        """Return the final node from this path.
        """
        return self._nodes[-1]

    @property
    def last_relationship(self):
        """Return the final relationship from this path, or :py:const:`None`
        if path length is zero.
        """
        if self._relationships:
            return self._relationships[-1]
        else:
            return None


class Index(rest.Resource):
    """An index within a `Neo4j <http://neo4j.org/>`_ database instance
    identified by a URI and/or a template URI. With a nod to Java generics,
    an index instance may hold either nodes or relationships by supplying the
    appropriate class directly to the constructor. For example:
    
        >>> from py2neo import neo4j
        >>> Index(neo4j.Node, "http://localhost:7474/db/data/index/node/index1")
        Index<Node>(u'http://localhost:7474/db/data/index/node/index1')
    
    By default, every index write operation will execute immediately but
    these may also be grouped into a batch in order to reduce HTTP calls. To
    create a batch, simply issue a :py:func:`start_batch` call, followed by the
    required :py:func:`add` and :py:func:`remove` calls and finally
    :py:func:`submit_batch`. A batch may be discarded at any time using
    :py:func:`discard_batch`.

    :param T:            a class object representing the type of entity contained within the index
    :param uri:          the URI of the index
    :param template_uri: a template URI for key and value substitution
    :param metadata:        an index of RESTful URIs
    """

    def __init__(self, T, uri=None, template_uri=None, metadata=None, **kwargs):
        rest.Resource.__init__(
            self,
            uri or template_uri.rpartition("/{key}/{value}")[0],
            metadata=metadata,
            **kwargs
        )
        self.__T = T
        self._base_uri, u0, u1 = self._uri.partition("/index")
        self._relative_uri = u0 + u1
        self._graph_database_service = GraphDatabaseService(self._base_uri)
        self._template_uri = template_uri or "{0}{1}{{key}}/{{value}}".format(
            uri,
            "" if uri.endswith("/") else "/"
        )
        self._relative_template_uri = "".join(self._template_uri.partition("/index")[1:])
        self._batch_uri = self._base_uri + "/batch"
        self._batch = None

    def __repr__(self):
        return '{0}<{1}>({2})'.format(
            self.__class__.__name__,
            self.__T.__name__,
            repr(self._uri)
        )

    def start_batch(self):
        """Start a new batch of index write operations.
        """
        self._batch = []

    def discard_batch(self):
        """Discard the current batch of index write operations.
        """
        self._batch = None

    def submit_batch(self):
        """Submit the current batch of index write operations.
        """
        self._post(self._batch_uri, self._batch)
        self._batch = None

    def add(self, entity, key, value):
        """Add an entry to this index under the specified `key` and `value`.
        If a batch has been started, this operation will not be submitted
        until :py:func:`submit_batch` has been called.
        """
        if self._graph_database_service._neo4j_version >= (1, 5):
            # new method
            if self._batch is None:
                self._post(self._uri, {
                    "uri": entity._uri,
                    "key": key,
                    "value": value
                })
            else:
                self._batch.append({
                    "method": "POST",
                    "to": self._relative_uri,
                    "body": {
                        "uri": entity._uri,
                        "key": key,
                        "value": value
                    },
                    "id": len(self._batch)
                })
        else:
            # legacy method
            if self._batch is None:
                self._post(self._template_uri.format(
                    key=_quote(key, ""),
                    value=_quote(value, "")
                ), entity._uri)
            else:
                self._batch.append({
                    "method": "POST",
                    "to": self._relative_template_uri.format(
                        key=_quote(key, ""),
                        value=_quote(value, "")
                    ),
                    "body": entity._uri,
                    "id": len(self._batch)
                })

    def remove(self, entity):
        """Remove the given entity from this index. The entity must have been
        retrieved from an index search and therefore contain an
        `_index_entry_uri` property. If a batch has been started, this
        operation will not be submitted until :py:func:`submit_batch` has been called.
        """
        if entity._index_uri != self._uri or entity._index_entry_uri is None:
            raise LookupError(entity)
        if self._batch is None:
            self._delete(entity._index_entry_uri)
        else:
            self._batch.append({
                'method': 'DELETE',
                'to': entity._relative_index_entry_uri,
                'id': len(self._batch)
            })

    def get(self, key, value):
        """Search the current index for items matching the supplied key/value
        pair; each pair may return zero or more matching items. The `value`
        parameter may also be a list allowing a batch search to be performed
        matching the specified `key` with each `value` in turn. In batch mode
        a list of lists will be returned, each top-level item
        corresponding to the `value` passed into the same position.
        """
        if isinstance(value, list):
            return [
                [
                    self.__T(
                        result['self'],
                        index_entry_uri=result['indexed'],
                        index_uri=self._uri
                    )
                    for result in item['body']
                ]
                for item in self._post(self._batch_uri, [
                    {
                        'method': 'GET',
                        'to': self._relative_template_uri.format(
                            key=_quote(key, ""),
                            value=_quote(value[i], "")
                        ),
                        'id': i
                    }
                    for i in range(len(value))
                ])
            ]
        else:
            return [
                self.__T(
                    item['self'],
                    index_entry_uri=item['indexed'],
                    index_uri=self._uri
                )
                for item in self._get(self._template_uri.format(
                    key=_quote(key, ""),
                    value=_quote(value, "")
                ))
            ]

    def query(self, query):
        """Query the current index for items using Lucene (or other) query
        syntax as available within the underlying implementation.
        """
        return [
            self.__T(item['self'])
            for item in self._get("{0}?query={1}".format(self._uri, _quote(query, "")))
        ]


class TraversalDescription(object):
    """Describes a graph traversal.
    """

    def __init__(self):
        warnings.warn("TraversalDescription is deprecated; please use Cypher "
                      "queries instead")
        self._description = {}

    def traverse(self, start_node):
        return Traverser(
            template_uri=start_node._lookup('traverse'),
            traversal_description=self._description
        )

    def order(self, selector):
        td = TraversalDescription()
        td._description = self._description
        td._description['order'] = selector
        return td

    def breadth_first(self):
        return self.order('breadth_first')

    def depth_first(self):
        return self.order('depth_first')

    def uniqueness(self, uniqueness):
        td = TraversalDescription()
        td._description = self._description
        td._description['uniqueness'] = uniqueness
        return td

    def relationships(self, type, direction=None):
        td = TraversalDescription()
        td._description = self._description
        if 'relationships' not in td._description:
            td._description['relationships'] = []
        if direction in ['in', 'incoming']:
            direction = 'in'
        elif direction in ['out', 'outgoing']:
            direction = 'out'
        elif direction:
            raise ValueError(direction)
        if direction:
            td._description['relationships'].append({
                'type': type,
                'direction': direction
            })
        else:
            td._description['relationships'].append({
                'type': type
            })
        return td

    def builtin_prune_evaluator(self, name):
        td = TraversalDescription()
        td._description = self._description
        td._description['prune_evaluator'] = {
            'language': 'builtin',
            'name': name
        }
        return td

    def prune_evaluator(self, language, body):
        td = TraversalDescription()
        td._description = self._description
        td._description['prune_evaluator'] = {
            'language': language,
            'body': body
        }
        return td

    def builtin_return_filter(self, name):
        td = TraversalDescription()
        td._description = self._description
        td._description['return_filter'] = {
            'language': 'builtin',
            'name': name
        }
        return td

    def return_filter(self, language, body):
        td = TraversalDescription()
        td._description = self._description
        td._description['return_filter'] = {
            'language': language,
            'body': body
        }
        return td

    def max_depth(self, depth):
        td = TraversalDescription()
        td._description = self._description
        td._description['max_depth'] = depth
        return td


class Traverser(rest.Resource):
    """An engine designed to traverse a `Neo4j <http://neo4j.org/>`_ database
    starting at a specific node.
    """

    class Order:

        BREADTH_FIRST = 'breadth_first'
        DEPTH_FIRST   = 'depth_first'

    def __init__(self, template_uri=None, traversal_description=None, metadata=None, **kwargs):
        warnings.warn("Traverser is deprecated; please use Cypher queries "
                      "instead")
        rest.Resource.__init__(self, None, metadata=metadata, **kwargs)
        self._template_uri = template_uri
        self._traversal_description = traversal_description

    @property
    def paths(self):
        """Return all paths from this traversal.
        """
        return [
            Path([
                Node(uri)
                for uri in path['nodes']
            ], [
                Relationship(uri)
                for uri in path['relationships']
            ])
            for path in self._post(
                self._template_uri.format(returnType='path'),
                self._traversal_description
            )
        ]

    @property
    def nodes(self):
        """Return all nodes from this traversal.
        """
        return [
            Node(node['self'])
            for node in self._post(
                self._template_uri.format(returnType='node'),
                self._traversal_description
            )
        ]

    @property
    def relationships(self):
        """Return all relationships from this traversal.
        """
        return [
            Relationship(relationship['self'])
            for relationship in self._post(
                self._template_uri.format(returnType='relationship'),
                self._traversal_description
            )
        ]
