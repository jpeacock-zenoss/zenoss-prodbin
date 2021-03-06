##############################################################################
# 
# Copyright (C) Zenoss, Inc. 2011, all rights reserved.
# 
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
# 
##############################################################################


class NmapExecutionError(Exception):
    """
    NmapExecutionError raised when there was a problem calling nmap.
    """

    def __init__(self, msg=None, exitCode=None, stdout=None, stderr=None, args=None):
        if msg is None:
            msg = "NmapExecution Error : %r, %r, %r" % (exitCode, stdout, stderr)
        super(NmapExecutionError, self).__init__(msg)
        self.exitCode = exitCode
        self.stdout = stdout
        self.stderr = stderr
        self.args = args
        
from lxml import etree as _etree

class NmapParsingError(_etree.XMLSyntaxError):
    """
    NmapParsingError is raise when there is an error parsing the nmap XML output.
    """
    pass


class NmapNotFound(Exception):
    """
    NmapNotFound raised when nmap is not found.
    """
    pass

class NmapNotSuid(Exception):
    """
    NmapNotFound raised when nmap is not found.
    """
    pass
