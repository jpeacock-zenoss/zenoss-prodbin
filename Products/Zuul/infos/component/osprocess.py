##############################################################################
# 
# Copyright (C) Zenoss, Inc. 2010, all rights reserved.
# 
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
# 
##############################################################################


from zope.interface import implements
from Products.Zuul.decorators import info
from Products.Zuul.interfaces import IOSProcessInfo
from Products.Zuul.infos.component import ComponentInfo, ServiceMonitor
from Products.Zuul.facades import getFacade
from zenoss.protocols.services.zep import ZepConnectionError

import logging
log = logging.getLogger('zen.osprocess')

class OSProcessInfo(ComponentInfo):
    implements(IOSProcessInfo)

    @property
    @info
    def processClass(self):
        # ZEN-3016: Get the primary acquisition. Processes should always have a class.
        klass = self._object.osProcessClass()
        if not klass:
            msg = 'Internal Error: OSProcess does not have an OSProcessClass: %s' % self.uid
            try:
                zep = getFacade('zep')
                device = self._object.device()
                zep.create(msg, 'Error', device.id, component=self.id, eventClass='/App')
            except ZepConnectionError:
                log.error(msg)
            return None
        return klass.primaryAq()

    @property
    def processName(self):
        return self._object.name()

    @property
    def description(self):
        return getattr(self.processClass, 'description', '')

    def getAlertOnRestart(self):
        return self._object.alertOnRestart()
    def setAlertOnRestart(self, value):
        if value is not None:
            self._object.zAlertOnRestart = value
        else:
            self._object.deleteZenProperty('zAlertOnRestart')
    alertOnRestart = property(getAlertOnRestart, setAlertOnRestart)

    def getFailSeverity(self):
        return self._object.getFailSeverity()
    def setFailSeverity(self, value):
        if value is not None:
            self._object.zFailSeverity = value
        else:
            self._object.deleteZenProperty('zFailSeverity')
    failSeverity = property(getFailSeverity, setFailSeverity)

    monitor = ServiceMonitor()

    @property
    def monitored(self):
        return self._object.monitored()
