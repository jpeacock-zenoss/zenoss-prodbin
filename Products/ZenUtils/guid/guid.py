###########################################################################
#
# This program is part of Zenoss Core, an open source monitoring platform.
# Copyright (C) 2010, Zenoss Inc.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 2 as published by
# the Free Software Foundation.
#
# For complete information please visit: http://www.zenoss.com/oss/
#
###########################################################################
__doc__="""guid

Generate a globally unique id that is used for events.
This is a wrapper around the library that is used in Python 2.5
and higher.
See http://zestyping.livejournal.com/157957.html for more info and
the code is available from http://zesty.ca/python/
"""
from uuid import uuid1, uuid3, uuid4, uuid5
from BTrees.OOBTree import OOBTree
from zope.event import notify
from zope.interface import implements
from zope.component import adapts
from .interfaces import IGloballyIdentifiable, IGlobalIdentifier, IGUIDManager

from Products.ZenUtils.guid.event import GUIDEvent

# Dictionary of known UUID types
known_uuid_types= {
  1:uuid1,
  3:uuid3,
  4:uuid4,
  5:uuid5,
}

def generate( uuid_type=4, *args, **kwargs ):
    """
    Generate an Universally Unique ID (UUID), according to RFC 4122.
    If an unknown uuid_type is provided, uses the UUID4 algorithm.

    >>> guids = [ generate() for x in range(100000) ]
    >>> guid_set = set( guids )
    >>> len(guids) == len(guid_set)
    True
    >>> len( str( generate() ) ) == 36
    True

    @param uuid_type: the type of UUID to generate
    @type uuid_type: range from 0 - 5
    @return: UUID
    @type: string
    """
    uuid_func = known_uuid_types.get(uuid_type, uuid4)
    return str(uuid_func(*args, **kwargs))


GUID_ATTR_NAME = '_guid'
GUID_TABLE_PATH = '/zport/dmd/guid_table'


class GlobalIdentifier(object):
    adapts(IGloballyIdentifiable)
    implements(IGlobalIdentifier)

    def __init__(self, context):
        self.context = context

    def getGUID(self):
        return getattr(self.context, GUID_ATTR_NAME, None)

    def setGUID(self, value):
        old = self.guid
        setattr(self.context, GUID_ATTR_NAME, value)
        notify(GUIDEvent(self.context, old, value))

    guid = property(getGUID, setGUID)

    def create(self, force=False):
        if self.guid is None or force:
            self.guid = generate()
        return self.guid


class GUIDManager(object):
    implements(IGUIDManager)

    _table_path = GUID_TABLE_PATH

    def __init__(self, context):
        self.context = context
        self.traverse = self.context.unrestrictedTraverse
        try:
            self.table = self.traverse(self._table_path)
        except (AttributeError, KeyError), e:
            parent, name = self._table_path.rsplit('/', 1)
            self.table = OOBTree()
            setattr(self.traverse(parent), name, self.table)

    def getPath(self, guid):
        return self.table.get(guid, None)

    def getObject(self, guid):
        path = self.getPath(guid)
        if path is not None:
            return self.traverse(path)

    def setPath(self, guid, path):
        self.table[guid] = path

    def setObject(self, guid, object):
        self.setPath(guid, object.getPrimaryUrlPath())

    def remove(self, guid):
        if guid in self.table:
            del self.table[guid]