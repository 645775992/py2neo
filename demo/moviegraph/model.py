#!/usr/bin/env python
# -*- encoding: utf-8 -*-


from py2neo.ogm import GraphObject, Property, Related, RelatedFrom


class Movie(GraphObject):
    __primarykey__ = "title"

    title = Property()
    tagline = Property()
    released = Property()

    actors = RelatedFrom("Person", "ACTED_IN")
    directors = RelatedFrom("Person", "DIRECTED")
    producers = RelatedFrom("Person", "PRODUCED")
    comments = Related("Comment", "COMMENT")

    def __lt__(self, other):
        return self.title < other.title


class Person(GraphObject):
    __primarykey__ = "name"

    name = Property()
    born = Property()

    acted_in = Related(Movie)
    directed = Related(Movie)
    produced = Related(Movie)

    def __lt__(self, other):
        return self.name < other.name


class Comment(GraphObject):

    name = Property()
    text = Property()
    date = Property()

    subject = RelatedFrom(Movie, "COMMENT")

    def __lt__(self, other):
        return self.date < other.date
