###########################################################################
#
# This program is part of Zenoss Core, an open source monitoring platform.
# Copyright (C) 2007, Zenoss Inc.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 2 as published by
# the Free Software Foundation.
#
# For complete information please visit: http://www.zenoss.com/oss/
#
###########################################################################

from socket import getfqdn
import pywintypes
import pythoncom

import Globals
from Products.ZenWin.WinCollector import WinCollector
from Products.ZenWin.WMIClient import WMIClient
from Products.ZenWin.Constants import TIMEOUT_CODE, ERROR_CODE_MAP
from Products.ZenEvents.ZenEventClasses import Status_Wmi, Status_WinService
from Products.ZenEvents import Event
from sets import Set

ERRtimeout = 1726

class zenwin(WinCollector):

    name = agent = "zenwin"
    attributes = WinCollector.attributes + ('winCycleInterval',)

    def __init__(self):
        WinCollector.__init__(self)
        self.statmsg = "Windows Service '%s' is %s"
        self.winCycleInterval = 60

    def mkevt(self, devname, svcname, msg, sev):
        "Compose an event"
        evt = dict(summary=msg,
                   eventClass=Status_WinService,
                   device=devname,
                   severity=sev,
                   agent=self.agent,
                   component=svcname,
                   eventGroup= "StatusTest",
                   manager=getfqdn())
        if sev > 0:
            self.log.critical(msg)
        else:
            self.log.info(msg)
        return evt

    def serviceStopped(self, device, name):
        self.log.warning('%s: %s stopped' % (device.id, name))
        if name not in device.services: return
        status, severity = device.services[name]
        device.services[name] = status + 1, severity
        msg = self.statmsg % (name, "down")
        self.sendEvent(self.mkevt(device.id, name, msg, severity))
        self.log.info("svc down %s, %s", device.id, name)
            
    def reportServices(self, device):
        for name, (status, severity) in device.services.items():
            if status > 0:
                msg = self.statmsg % (name, "down")
                self.sendEvent(self.mkevt(device.id, name, msg, severity))
            
    def serviceRunning(self, device, name):
        if name not in device.services: return
        status, severity = device.services[name]
        device.services[name] = 0, severity
        if status != 0:
            self.log.info('%s: %s running' % (device.id, name))
            msg = self.statmsg % (name, "up")
            self.sendEvent(self.mkevt(device.id, name, msg, 0))
            self.log.info("svc up %s, %s", device.id, name)


    def scanDevice(self, device):
        if not device.services:
            return None
        wql = "select Name from Win32_Service where State='Running'"
        wmic = WMIClient(device)
        wmic.connect()
        q = wmic.query(dict(query=wql))
        running = Set([ svc.name for svc in q['query'] ])
        monitored = Set(device.services.keys())
        self.log.debug("services: %s", monitored)
        for name in monitored - running:
            self.serviceStopped(device, name)
        for name in monitored & running:
            self.serviceRunning(device, name)
        wmic.close()


    def processDevice(self, device):
        wql = ("""SELECT * FROM __InstanceModificationEvent within 5 where """
               """TargetInstance ISA 'Win32_Service' """)
        
        # device won't have any attributes
        if not device.plugins: return
        try:
            w = self.watchers.get(device.id, None)
            if not w:
                self.scanDevice(device)
                self.deviceUp(device)
                self.watchers[device.id] = w = self.getWatcher(device, wql)
            else:
                self.reportServices(device)
                self.log.debug("Querying %s", device.id)
                s = w.nextEvent(int(self.options.queryTimeout))
                self.deviceUp(device)
                if not s.state:
                    return
                if s.state == 'Stopped':
                    self.serviceStopped(device, s.name)
                if s.state == 'Running':
                    self.serviceRunning(device, s.name)
        except pywintypes.com_error, e:
            code,txt,info,param = e
            if info:
                wcode, source, descr, hfile, hcont, scode = info
                scode = abs(scode)
                if wcode == ERRtimeout:
                    return
                self.log.debug("Codes: %r" % (info,))
                if scode != TIMEOUT_CODE:
                    msg = '%d: %s' % (code, txt)
                    msg = ERROR_CODE_MAP.get(str(scode), [None, msg])[1]
                    self.deviceDown(device, msg)
    def processLoop(self):
        pythoncom.PumpWaitingMessages()
        for device in self.devices:
            if device.id in self.wmiprobs:
                self.log.debug("WMI problems on %s: skipping" % device.id)
                continue
            try:
                try:
                    self.processDevice(device)
                except Exception, ex:
                    self.deviceDown(device, str(ex))
            finally:
                self.niceDoggie(self.winCycleInterval)

    def deviceDown(self, device, message):
        if device.id in self.watchers:
            w = self.watchers.pop(device.id)
            w.close()
        msg = self.printComErrorMessage(message)
        if not msg:
            msg = "WMI connect error on %s: %s" % (device.id, message)
        self.sendEvent(dict(summary=msg,
                            eventClass=Status_Wmi,
                            device=device.id,
                            severity=Event.Error,
                            agent=self.agent,
                            component=self.name))
        self.wmiprobs.append(device.id)
        self.log.warning("WMI Connection to %s went down" % device.id)

    def deviceUp(self, device):
        if device.id in self.wmiprobs:
            self.wmiprobs.remove(device.id)
            self.log.info("WMI Connection to %s up" % device.id)
            msg = "WMI connection to %s up." % device.id
            self.sendEvent(dict(summary=msg,
                                eventClass=Status_Wmi,
                                device=device.id,
                                severity=Event.Clear,
                                agent=self.agent,
                                component=self.name))

    def updateConfig(self, cfg):
        WinCollector.updateConfig(self, cfg)
        self.heartbeatTimeout = self.winCycleInterval * 3

    def fetchDevices(self, driver):
        yield self.configService().callRemote('getDeviceListByMonitor',
                                       self.options.monitor)
        yield self.configService().callRemote('getDeviceConfigAndWinServices', 
            driver.next())
        self.updateDevices(driver.next())

    def cycleInterval(self):
        return self.winCycleInterval
        
    def buildOptions(self):
        WinCollector.buildOptions(self)


if __name__ == "__main__":
    zw = zenwin()
    zw.run()
