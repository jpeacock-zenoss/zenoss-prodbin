import types
from AccessControl import ClassSecurityInfo
from Globals import InitializeClass

from EventManagerBase import EventManagerBase
from MySqlSendEvent import MySqlSendEventMixin
from Exceptions import *

def manage_addMySqlEventManager(context, id=None, history=False, REQUEST=None):
    '''make an MySqlEventManager'''
    if not id: 
        id = "ZenEventManager"
        if history: id = "ZenEventHistory"
    evtmgr = MySqlEventManager(id) 
    context._setObject(id, evtmgr)
    evtmgr = context._getOb(id)
    if history: 
        evtmgr.statusTable = "history"
    evtmgr.installIntoPortal()
    if REQUEST:
        REQUEST['RESPONSE'].redirect(context.absolute_url()+'/manage_main')



class MySqlEventManager(MySqlSendEventMixin, EventManagerBase):

    portal_type = meta_type = 'MySqlEventManager'
   
    backend = "mysql"

    security = ClassSecurityInfo()
    
    def getEventSummary(self, where="", acked=None):
        """
        Return a list of tuples with number of events
        and the color of the severity that the number represents.
        """ 
        select = "select count(*) from %s where " % self.statusTable
        select += where
        if where: select += " and "
        select += "%s = %%s" % self.severityField
        #print select
        sevsum = self.checkCache(select)
        if sevsum: return sevsum
        db = self.connect()
        curs = db.cursor()
        sevsum = []
        for name, value in self.getSeverities():
            curs.execute(select, (value,))
            sevsum.append((self.getEventCssClass(value), curs.fetchone()[0]))
        db.close()
        self.addToCache(select, sevsum)
        self.cleanCache()
        return sevsum


InitializeClass(MySqlEventManager)
