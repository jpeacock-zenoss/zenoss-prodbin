#################################################################
#
#   Copyright (c) 2002 Zenoss, Inc. All rights reserved.
#
#################################################################

__doc__="""Software

Software represents a software vendor's product.

$Id: Software.py,v 1.5 2003/03/08 18:34:24 edahl Exp $"""

__version__ = "$Revision: 1.5 $"[11:-2]

from Globals import DTMLFile
from Globals import InitializeClass
from AccessControl import ClassSecurityInfo

from AccessControl import Permissions as permissions

from Products.ZenRelations.RelSchema import *

from MEProduct import MEProduct
from ZenDate import ZenDate

def manage_addSoftware(context, id, title = None, REQUEST = None):
    """make a Software"""
    d = Software(id, title)
    context._setObject(id, d)
    if REQUEST is not None:
        REQUEST['RESPONSE'].redirect(context.absolute_url()+'/manage_main') 
                                     

addSoftware = DTMLFile('dtml/addSoftware',globals())


class Software(MEProduct):
    """Software object"""
    portal_type = meta_type = 'Software'

    procRegex = ""
    monitorProc = False

    _properties = (
        {'id':'procRegex', 'type':'string', 'mode':'w'},
        {'id':'monitorProc', 'type':'boolean', 'mode':'w'},
        {'id':'installDate', 'type':'date', 'mode':''},
    )

    _relations = MEProduct._relations + (
        ("os", ToOne(ToManyCont, "OperatingSystem", "software")),
    )

    factory_type_information = ( 
        { 
            'id'             : 'Software',
            'meta_type'      : 'Software',
            'description'    : """Class to manage product information""",
            'icon'           : 'Software_icon.gif',
            'product'        : 'ZenModel',
            'factory'        : 'manage_addSoftware',
            'immediate_view' : 'viewProductOverview',
            'actions'        :
            ( 
                { 'id'            : 'overview'
                , 'name'          : 'Overview'
                , 'action'        : 'viewSoftwareOverview'
                , 'permissions'   : (
                  permissions.view, )
                },
                { 'id'            : 'viewHistory'
                , 'name'          : 'Changes'
                , 'action'        : 'viewHistory'
                , 'permissions'   : (
                  permissions.view, )
                },
            )
          },
        )

    security = ClassSecurityInfo()

    def __init__(self, id, title=""):
        MEProduct.__init__(self, id, title)
        self._installDate = ZenDate("1968/1/8")

    
    def __getattr__(self, name):
        if name == 'installDate':
            return self._installDate.getDate()
        else:
            raise AttributeError, name

    
    def _setPropValue(self, id, value):
        """override from PerpertyManager to handle checks and ip creation"""
        self._wrapperCheck(value)
        if id == 'installDate':
            self.setInstallDate(value)
        else:    
            MEProduct._setPropValue(self, id, value)


    security.declareProtected('Change Device', 'setProduct')
    def setProduct(self, productName,  manufacturer="Unknown", 
                    newProductName="", REQUEST=None, **kwargs):
        """Set the product class of this software.
        """
        if not manufacturer: manufacturer = "Unknown"
        if newProductName: productName = newProductName
        prodobj = self.getDmdRoot("Manufacturers").createSoftwareProduct(
                                    productName, manufacturer, **kwargs)
        self.productClass.addRelation(prodobj)
        if REQUEST:
            REQUEST['message'] = ("Set Manufacturer %s and Product %s at time:" 
                                    % (manufacturer, productName))
            return self.callZenScreen(REQUEST)


    def setProductKey(self, prodKey):
        """Set the product class of this software by its productKey.
        """
        self.productKey = prodKey
        prodobj=self.getDmdRoot("Manufacturers").createSoftwareProduct(prodKey)
        self.productClass.addRelation(prodobj)


    def name(self):
        """Return the name of this software (from its softwareClass)
        """
        pclass = self.productClass()
        if pclass: return pclass.name
        return ""


    def version(self):
        """Return the verion of this software (from its softwareClass)
        """
        pclass = self.productClass()
        if pclass: return pclass.version
        return ""
       

    def build(self):
        """Return the build of this software (from its softwareClass)
        """
        pclass = self.productClass()
        if pclass: return pclass.build
        return ""
       

    def getInstallDateObj(self):
        """Return the install date as a DateTime object.
        """
        return self._installDate.getDate()


    def getInstallDate(self):
        """Return the install date in the form 'YYYY/MM/DD HH:MM:SS'
        """
        return self._installDate.getString()


    def setInstallDate(self, value):
        """Set the install date should be string in form 'YYYY/MM/DD HH:MM:SS'
        """
        self._installDate.setDate(value) 


    def device(self):
        """Return our Device for DeviceResultInt.
        """
        return self.os().device()

    
InitializeClass(Software)
