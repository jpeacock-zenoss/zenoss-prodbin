from zope.component import queryUtility
from zope.i18n.interfaces import ITranslationDomain
from zope.i18n.negotiator import negotiator
from Products.Five.browser import BrowserView

from Products.ZenUtils.json import json

def getDomainMessages(name, request):
    result = {}
    domain = queryUtility(ITranslationDomain, name)
    if domain:
        langs = domain._catalogs.keys()
        lang = negotiator.getLanguage(langs, request)
        if lang:
            path = domain._catalogs[lang][0]
            cat = domain._data[path]
            data = cat._catalog._catalog
            # Strip out empty key
            result = dict((k,v) for k,v in data.iteritems() if k)
    return result


class I18N(BrowserView):
    def __call__(self):
        tpl = "Zenoss.i18n._data = %s;"
        # Get messages for general keys
        msgs = getDomainMessages('zenoss', self.request)
        # Add messages for the domain
        dname = self.request.get('domain')
        if dname:
            msgs.update(getDomainMessages(dname, self.request))
        return tpl % json(msgs)

