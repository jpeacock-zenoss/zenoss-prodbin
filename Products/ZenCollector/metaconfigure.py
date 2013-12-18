##############################################################################
# 
# Copyright (C) Zenoss, Inc. 2013, all rights reserved.
# 
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
# 
##############################################################################

from zope.configuration.config import (
    IConfigurationContext, GroupingContextDecorator
)
from zope.configuration.exceptions import ConfigurationError
from zope.configuration.fields import GlobalObject
from zope.component.interfaces import implements
from zope.component.zcml import utility
from zope.interface import Interface
from zope.interface.verify import verifyClass
from zope.schema import Text, TextLine

from .daemon import CollectorDaemon, CollectorDaemonFactory
from .interfaces import (
    ICollectorFactory, ICollector, ICollectorPreferences, ITaskSplitter,
    IScheduledTaskFactory, IScheduledTask
)
from .tasks import SimpleTaskFactory, SimpleTaskSplitter


class ICollectorDaemonDirective(Interface):
    """
    Registers a collector daemon factory as a utility.
    """
    name = TextLine(
            title=u"Name",
            description=u"Name of the collector daemon"
        )

    description = Text(
            title=u"Description",
            description=u"Short description of collector daemon"
        )

    preferences = GlobalObject(
            title=u"Preferences",
            description=u"Collector daemon preferences class."
        )

    task = GlobalObject(
            title=u"Task",
            description=u"Collector daemon task class."
        )


class ITaskFactoryDirective(Interface):
    class_ = GlobalObject(title=u"IScheduledTaskFactory class")


class ITaskSplitterDirective(Interface):
    class_ = GlobalObject(title=u"ITaskSplitter class")


class CollectorDaemonDirective(GroupingContextDecorator):
    implements(IConfigurationContext, ICollectorDaemonDirective)

    def __init__(self, context, name, description, preferences, task):
        self.context = context
        self.name = name
        self.description = description
        self.preferences = preferences
        self.task = task
        self.taskfactory = SimpleTaskFactory
        self.tasksplitter = SimpleTaskSplitter

    def after(self):
        factory = CollectorDaemonFactory(
                CollectorDaemon, self.preferences, self.task,
                self.taskfactory, self.tasksplitter,
                self.name, self.description, (ICollector,)
            )
        utility(
            self.context, provides=ICollectorFactory,
            component=factory, name=self.name
        )


def handleTaskFactoryDirective(context, class_):
    context.context.taskfactory = class_


def handleTaskSplitterDirective(context, class_):
    context.context.tasksplitter = class_

