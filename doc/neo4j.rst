:mod:`neo4j` Module
===================

.. automodule:: py2neo.neo4j

Connecting to a Graph
---------------------

A default installation of Neo4j will use the URI below for the root of the
graph database service:

.. autoattribute:: py2neo.neo4j.DEFAULT_URI

.. autoclass:: py2neo.neo4j.GraphDatabaseService
    :members:
    :show-inheritance:

Authentication
--------------

.. autofunction:: py2neo.neo4j.authenticate

Nodes and Relationships
-----------------------

.. autoclass:: py2neo.neo4j.PropertyContainer
    :members:

.. autoclass:: py2neo.neo4j.Node
    :members:
    :show-inheritance:

.. autoclass:: py2neo.neo4j.Relationship
    :members:
    :show-inheritance:

Indexes
-------

.. autoclass:: py2neo.neo4j.Index
    :members:
    :show-inheritance:

Paths
-----

.. autoclass:: py2neo.neo4j.Path
    :members:
    :show-inheritance:
