###########################################################################
#
# This program is part of Zenoss Core, an open source monitoring platform.
# Copyright (C) 2008, Zenoss Inc.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 2 as published by
# the Free Software Foundation.
#
# For complete information please visit: http://www.zenoss.com/oss/
#
###########################################################################

__doc__ = "Manage ZenPacks"

import Globals
from Products.ZenUtils.ZenScriptBase import ZenScriptBase
from Products.ZenUtils.Utils import cleanupSkins, zenPath
from Products.ZenModel.ZenPack import ZenPackException, \
                                        ZenPackNotFoundException, \
                                        ZenPackNeedMigrateException
from Products.ZenModel.ZenPack import ZenPackDependentsException
from Products.ZenModel.ZenPack import ZenPack
import Products.ZenModel.ZenPackLoader as ZPL
import transaction
import os, sys
import pkg_resources
import shutil
import string
import tempfile
import subprocess
import socket

#import zenpacksupport

FQDN = socket.getfqdn()

ZEN_PACK_INDEX_URL = ''

# All ZenPack eggs have to define exactly one entry point in this group.
ZENPACK_ENTRY_POINT = 'zenoss.zenpacks'

########################################
#   ZenPack Creation
########################################

def CreateZenPack(zpId):
    """
    Create the zenpack in the filesystem.
    The zenpack is not installed in Zenoss, it is simply created in
    the $ZENHOME/ZenPacks directory.  Usually this should be followed
    with a "zenpack install" call.
    zpId should already be valid, scrubbed value.
    """
    parts = zpId.split('.')
    
    # Copy template to $ZENHOME/ZenPacks
    srcDir = zenPath('Products', 'ZenModel', 'ZenPackTemplate')
    devDir = zenPath('ZenPacks')
    if not os.path.exists(devDir):
        os.mkdir(devDir, 0750)
    destDir = os.path.join(devDir, zpId)
    shutil.copytree(srcDir, destDir, symlinks=False)
    os.system('find %s -name .svn | xargs rm -rf' % destDir)

    # Write setup.py
    packages = []
    for i in range(len(parts)):
        packages.append('.'.join(parts[:i+1]))
    mapping = dict(
        NAME = zpId,
        VERSION = '1.0',
        AUTHOR = '',
        LICENSE = '',
        NAMESPACE_PACKAGES = packages[:-1],
        PACKAGES = packages,
        INSTALL_REQUIRES = [],
        COMPAT_ZENOSS_VERS = '',
        )
    WriteSetup(os.path.join(destDir, 'setup.py'), mapping)

    # Create subdirectories
    base = destDir
    for part in parts[:-1]:
        base = os.path.join(base, part)
        os.mkdir(base)
        f = open(os.path.join(base, '__init__.py'), 'w')
        f.write("__import__('pkg_resources').declare_namespace(__name__)\n")
        f.close()
    base = os.path.join(base, parts[-1])
    shutil.move(os.path.join(destDir, 'CONTENT'), base)
    
    # Create the skins subdirs
    skinsDir = os.path.join(base, 'skins', zpId)
    os.mkdir(skinsDir)
    
    # Stick a placeholder in the skins dir so that the egg will include
    # the dir even if empty.
    f = file(os.path.join(skinsDir, 'placeholder.txt'), 'w')
    f.close()

    return destDir


def WriteSetup(setupPath, values):
    """
    """
    f = file(setupPath, 'r')
    lines = f.readlines()
    f.close()

    newLines = []
    for i, line in enumerate(lines):
        if line.startswith('STOP_REPLACEMENTS'):
            newLines += lines[i:]
            break
        key = line.split('=')[0].strip()
        if values.has_key(key):
            value = values[key]
            if isinstance(value, basestring):
                fmt = "%s = '%s'\n"
            else:
                fmt = "%s = %s\n"
            newLines.append(fmt % (key, value))
        else:
            newLines.append(line)
    
    f = file(setupPath, 'w')
    f.writelines(newLines)
    f.close()


def CanCreateZenPack(dmd, zpId):
    """
    Return tuple (bool, string) where first element is true if a new zenpack
    can be created with the given info and false if not.  If first element
    is True then the second part of the tuple contains the scrubbed ZenPack id.
    If the first part is False then the second contains an explanatory
    message.
    """
    # Check if id and package looks reasonable
    (allowable, idOrMsg) = ScrubZenPackId(zpId)
    if allowable:
        zpId = idOrMsg
    else:
        return (False, idOrMsg)

    # Is the id already in use?
    if dmd:
        if zpId in dmd.ZenPackManager.packs.objectIds():
            return (False, 'A ZenPack named %s already exists.' % zpId)

    # Is there another zenpack in the way?
    # Now that zenpacks are created in $ZENHOME/ZenPacks instead of 
    # $ZENHOME/ZenPackDev this may no longer be necessary because a
    # zp in the way should be installed and caught by the already in use
    # check above.
    if os.path.exists(zenPath('ZenPacks', zpId)):
        return (False, 'A directory named %s already exists' % zpId +
                        ' in $ZENHOME/ZenPacks.  Use a different name'
                        ' or remove that directory.')

    return (True, idOrMsg)


def ScrubZenPackId(name):
    """
    If the given name conforms to ZenPack naming rules, or can easily be
    modified to do so, then return (True, scrubbedName) where scrubbedName
    is either name or a slightly modified name.  If the given name does
    not conform to naming rules and we can't easily modify it to do so
    then return (False, errorMsg) where errorMsg describes why name
    is unacceptable.
    """
    parts = name.split('.')

    # Remove leading dots, trailing dots, adjacent dots and strip whitespace
    # from each part
    parts = [p.strip() for p in parts]
    parts = [p for p in parts if p]

    # Add/fix leading 'ZenPacks'
    if parts[0] != 'ZenPacks':
        if parts[0].lower() == 'zenpacks':
            parts[0] = 'ZenPacks'
        else:
            parts.insert(0, 'ZenPacks')

    # Must be at least 3 parts
    if len(parts) < 3:
        return (False, 'ZenPack names must contain at least three package '
                'names separated by periods.')

    # Each part must start with a letter
    for p in parts:
        if p[0] not in string.letters:
            return (False, 'Each package name must start with a letter.')

    # Only letters, numbers and underscores in each part
    allowable = string.letters + string.digits + '_'
    for p in parts:
        for c in p:
            if c not in allowable:
                return (False, 'Package names may only contain letters, '
                        'numbers and underscores.')

    return (True, '.'.join(parts))


########################################
#   ZenPack Installation
########################################


def InstallEggAndZenPack(dmd, eggPath, link=False, 
                            filesOnly=False, sendEvent=True):
    """
    Installs the given egg, instantiates the ZenPack, installs in
    dmd.ZenPackManager.packs, and runs the zenpacks's install method.
    Returns a list of ZenPacks that were installed.
    """
    try:
        zenPackName = InstallEgg(dmd, eggPath, link=link)
        zenPacks = DiscoverAndInstall(dmd, zenPackName)
    except:
        if sendEvent:
            ZPEvent(dmd, 4, 'Error installing ZenPack %s' % eggPath,
                '%s: %s' % sys.exc_info()[:2])
        raise
    if sendEvent:
        zenPackIds = [zp.id for zp in zenPacks]
        if zenPackName in zenPackIds:
            ZPEvent(dmd, 2, 'Installed ZenPacks %s' % ','.join(zenPackIds))
        else:
            ZPEvent(dmd, 4, 'Unable to install ZenPack %s' % zenPackName)
    return zenPacks


def InstallEgg(dmd, eggPath, link=False):
    """
    Install the given egg and add to the current working set.
    This does not install the egg as a ZenPack.
    """
    eggPath = os.path.abspath(eggPath)
    zenPackDir = zenPath('ZenPacks')
    eggInZenPacksDir = eggPath.startswith(zenPackDir + '/')
    
    # On upgrade, if location is switching, we should delete the old
    # location zenpack.deleteFilesOnRemove().  This way people could move
    # zenpacks in development out of ZenPacks dir with a simple reinstall
    # from another location.
    
    # Make sure $ZENHOME/ZenPacks exists
    CreateZenPacksDir()

    # Install the egg
    if link:
        cmd = ('python setup.py develop '
                '--site-dirs=%s ' % zenPackDir +
                '-d %s' % zenPackDir)
        p = subprocess.Popen(cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            shell=True,
                            cwd=eggPath)
        p.wait()
        errors = p.stderr.read()
        if errors:
            sys.stderr.write('%s\n' % errors)
    else:
        cmd = 'easy_install --always-unzip --site-dirs=%s -d %s %s' % (
                    zenPackDir,
                    zenPackDir,
                    eggPath)
        p = subprocess.Popen(cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            shell=True)
        p.wait()
        eggName = os.path.split(eggPath)[1]
        eggPath = os.path.join(zenPackDir, eggName)

    # Add egg to working_set
    zenPackName = AddDistToWorkingSet(eggPath)

    return zenPackName


def InstallDistAsZenPack(dmd, dist, filesOnly=False):
    """
    Given an installed dist, install it into Zenoss as a ZenPack.
    Return the ZenPack instance.
    """
    # Instantiate ZenPack
    entryMap = pkg_resources.get_entry_map(dist, ZENPACK_ENTRY_POINT)
    if not entryMap or len(entryMap) > 1:
        raise ZenPackException('A ZenPack egg must contain exactly one'
                ' zenoss.zenpacks entry point.  This egg appears to contain'
                ' %s such entry points.' % len(entryMap))
    packName, packEntry = entryMap.items()[0]
    module = packEntry.load()
    if hasattr(module, 'ZenPack'):
        zenPack = module.ZenPack(packName)
    else:
        zenPack = ZenPack(packName)
    zenPack.eggPack = True
    CopyMetaDataToZenPackObject(dist, zenPack)

    if filesOnly:
        for loader in (ZPL.ZPLDaemons(), ZPL.ZPLBin(), ZPL.ZPLLibExec()):
            loader.load(zenPack, None)
    else:
        existing = dmd.ZenPackManager.packs._getOb(packName, None)
        if existing:
            CopyMetaDataToZenPackObject(dist, existing)
            if existing.isEggPack():
                existing.upgrade(dmd)
                # Remove previous dist if in a different location
            else:
                # Upgrading from old-style to egg
                existing.__class__ = zenPack.__class__
                zenPack = existing
                zenPack.eggPack = True
                zenPack.upgrade(dmd)
                # Remove from Products?
        else:
            dmd.ZenPackManager.packs._setObject(packName, zenPack)
            zenPack = dmd.ZenPackManager.packs._getOb(packName)
            zenPack.install(dmd)

    cleanupSkins(dmd)
    transaction.commit()
    return zenPack


def DiscoverAndInstall(dmd, zenPackId):
    """
    Discover installed eggs that provide zenoss.zenpacks entry points.
    Install into Zenoss those that aren't already.
    """
    dists = DiscoverEggs(dmd, zenPackId)
    installed = []
    for d in dists:
        installed.append(InstallDistAsZenPack(dmd, d))
    return installed


def DiscoverEggs(dmd, zenPackId):
    """
    Find installed eggs that provide a zenoss.zenpacks entry point.
    Return a list of distributions whose ZenPacks need to be installed
    or upgraded.  The list is sorted into the order in which this needs to
    happen.
    """
    # Create a set of all available zenoss.zenpack entries that aren't
    # already installed in zenoss or need to be upgraded in zenoss.
    entries = set()
    parse_version = pkg_resources.parse_version
    for entry in pkg_resources.iter_entry_points(ZENPACK_ENTRY_POINT):
        packName = entry.name
        packVers = entry.dist.version
        existing = dmd.ZenPackManager.packs._getOb(packName, None)
        if existing and existing.isEggPack():
            # We use >= to allow migrate to be run on currently installed
            # zenpacks whose version has been changed or for whom new
            # migrates have been added.
            if parse_version(packVers) >= parse_version(existing.version):
                entries.add(entry)
        else:
            entries.add(entry)

    # Starting with the entry representing zenPackId create a list of
    # all entrypoints

    # orderedEntries lists entries in the opposite order of that in which
    # they need to be installed.  This is simply for convenience of using
    # .append() in code below.
    orderedEntries = []
    entriesByName = dict([(e.name, e) for e in entries])

    def AddEntryAndProcessDeps(e):
        orderedEntries.append(e)
        for name in [r.project_name for r in e.dist.requires()]:
            if name in [e.name for e in orderedEntries]:
                # This entry depends on something that we've already processed.
                # This might be a circular dependency, might not be.
                # We are just going to bail however.  This should be
                # very unusual and the user can install deps first to work
                # around.
                raise ZenPackException('Unable to resolve ZenPack dependencies.'
                    ' Try installing dependencies first.')
            if name in entriesByName:
                # The requirement is an entry that has not yet been processed
                # here.  Add it to the list of entries to install/upgrade.
                AddEntryAndProcessDeps(entriesByName[name])
            else:
                # The requirement is not in the entries generated above.
                # This either means that the dep is already installed (this
                # is likely) or that easy_install missed something and the dep
                # is not installed/available (this should be unlikely.)
                pass

    if zenPackId not in entriesByName:
        if zenPackId in dmd.ZenPackManager.packs.objectIds():
            return []
        else:
            raise ZenPackException('Unable to discover ZenPack named %s' %
                                    zenPackId)
    AddEntryAndProcessDeps(entriesByName[zenPackId])
    orderedEntries.reverse()
    return [e.dist for e in orderedEntries]


def AddDistToWorkingSet(distPath):
    """
    Given the path to a dist (an egg) add it to the current working set.
    This is basically a pkg_resources-friendly way of adding it to
    sys.path.
    If the dist was added successfully then return the name of the
    dist project, otherwise return None
    """
    distGen = pkg_resources.find_distributions(distPath)
    try:
        dist = distGen.next()
    except StopIteration:
        return None
    pkg_resources.working_set.add(dist)
    pkg_resources.require(dist.project_name)
    return dist.project_name


def ReadZenPackInfo(dist):
    """
    Return a dictionary containing the egg metadata
    """
    info = {}
    if dist.has_metadata('PKG-INFO'):
        lines = dist.get_metadata('PKG-INFO')
        for line in pkg_resources.yield_lines(lines):
            key, value = line.split(':', 1)
            info[key.strip()] = value.strip()
    if dist.has_metadata('zenpack_info'):
        lines = dist.get_metadata('zenpack_info')
        for line in pkg_resources.yield_lines(lines):
            key, value = line.split(':', 1)
            info[key.strip()] = value.strip()
    return info


def CopyMetaDataToZenPackObject(dist, pack):
    """
    Copy metadata type stuff from the distribution to the zp object.
    """
    # Version
    pack.version = dist.version

    # Egg Info
    info = ReadZenPackInfo(dist)
    pack.author = info.get('Author', '')
    if pack.author == 'UNKNOWN':
        pack.author = ''
    pack.compatZenossVers = info.get('compatZenossVers', '')

    # Requires
    pack.dependencies = {}
    for r in dist.requires():
        name = r.project_name
        spec = str(r)[len(name):]
        pack.dependencies[name] = spec


def CreateZenPacksDir():
    """
    Make sure $ZENHOME/ZenPacks exists
    """
    zpDir = zenPath('ZenPacks')
    if not os.path.isdir(zpDir):
        os.mkdir(zpDir, 0750)


########################################
#   Zenoss.Net
########################################


def FetchAndInstallZenPack(dmd, zenPackName, zenPackVersion='', sendEvent=True):
    """
    Fetch the named zenpack and all its dependencies and install them.
    Return a list of the ZenPacks that were installed.
    """
    try:
        FetchZenPack(zenPackName, zenPackVersion)
        zenPacks = DiscoverAndInstall(dmd, zenPackName)
    except:
        if sendEvent:
            ZPEvent(dmd, 4, 'Failed to install ZenPack %s' % zenPackName,
                '%s: %s' % sys.exc_info()[:2])
        raise
    if sendEvent:
        zenPackIds = [z.id for z in zenPacks]
        if zenPackIds:
            ZPEvent(dmd, 2, 'Installed ZenPacks: %s' % ', '.join(zenPackIds))
        if zenPackName not in zenPackIds:
            ZPEvent(dmd, 4, 'Unable to install ZenPack %s' % zenPackName)
    return zenPacks


def FetchZenPack(zenPackName, zenPackVersion=''):
    """
    Use easy_install to retrieve the given zenpack and any dependencies.
    easy_install will install the eggs, but does not install them into
    Zenoss as ZenPacks.
    Return list of project_names of installed distributions.  These are
    probably all ZenPacks, but possibly not.
    """
    from setuptools.command import easy_install
    
    # Make sure $ZENHOME/ZenPacks exists
    CreateZenPacksDir()
    
    # Create temp file for easy_install to write results to
    _, tempPath = tempfile.mkstemp(prefix='zenpackcmd-easyinstall')
    # eggPaths is a set of paths to eggs that were installed.  We need to
    # add them to the current workingset so we can discover their
    # entry points.
    eggPaths = set()
    try:
        # Execute the easy_install
        args = ['--site-dirs', zenPath('ZenPacks'),
            '-d', zenPath('ZenPacks'),
            '-i', ZEN_PACK_INDEX_URL,
            '--record', tempPath,
            '--quiet',
            zenPackName]
        easy_install.main(args)
        # Collect the paths for eggs that were installed
        f = open(tempPath, 'r')
        marker = '.egg/'
        markerOffset = len(marker)-1
        for l in f.readlines():
            i = l.find(marker)
            if i > 0:
                eggPaths.add(l[:i+markerOffset])
    finally:
        os.remove(tempPath)
    # Add any installed eggs to the current working set
    distProjectNames = []
    for path in eggPaths:
        projectName = AddDistToWorkingSet(path)
        distProjectNames.append(projectName)
    return distProjectNames


def UploadZenPack(dmd, packName, project, description, znetUser, znetPass):
    """
    Upload the specified zenpack to the given project.
    Project is a string of the form 'enterprise/myproject' or
    'community/otherproject'.
    """
    zp = dmd.ZenPackManager.packs._getOb(packName, None)
    if not zp:
        raise ZenPackException('No ZenPack named %s' % packName)

    # Export the zenpack
    fileName = zp.manage_exportPack()
    filePath = zenPath('export', fileName)

    # Login to Zenoss.net
    from DotNetCommunication import DotNetSession
    session = DotNetSession()
    userSettings = dmd.ZenUsers.getUserSettings()
    session.login(znetUser, znetPass)

    # Upload
    zpFile = open(zenPath('export', fileName), 'r')
    try:
        response = session.open('%s/createRelease' % project.strip('/'), {
                'description': description,
                'fileStorage': zpFile,
                })
    finally:
        zpFile.close()
    if response:
        result = response.read()
        if "'success':true" not in result:
            raise ZenPackException('Upload failed')
    else:
        raise ZenPackException('Failed to connect to Zenoss.net')
    return


########################################
#   ZenPack Removal
########################################


def RemoveZenPack(dmd, packName, filesOnly=False, skipDepsCheck=False,
                    leaveObjects=False, sendEvent=True):
    """
    Remove the given ZenPack from Zenoss.
    Whether the ZenPack will be removed from the filesystem or not
    depends on the result of the ZenPack's shouldDeleteFilesOnRemoval method.
    """
    try:
        if filesOnly:
            skipDepsCheck = True

        # Check for dependency implications here?
        if not skipDepsCheck:
            deps = GetDependents(dmd, packName)
            if deps:
                raise ZenPackDependentsException('%s cannot be removed ' % packName +
                        'because it is required by %s' % ', '.join(deps))

        if not filesOnly:
            # Fetch the zenpack, call its remove() and remove from packs
            zp = None
            try:
                zp = dmd.ZenPackManager.packs._getOb(packName)
            except AttributeError, ex:
                raise ZenPackNotFoundException('No ZenPack named %s is installed' %
                                                packName)
            zp.remove(dmd, leaveObjects)
            dmd.ZenPackManager.packs._delObject(packName)

        # Uninstall the egg and possibly delete it
        # If we can't find the distribution then apparently the zp egg itself is
        # missing.  Continue on with the removal and swallow the
        # DistributionNotFound exception
        try:
            dist = zp.getDistribution()
        except pkg_resources.DistributionNotFound:
            dist = None
        if dist:
            # Determine deleteFiles before develop -u gets called.  Once
            # it is called the egg has problems figuring out some of it's state.
            deleteFiles = zp.shouldDeleteFilesOnRemoval()
            if zp.isDevelopment():
                zenPackDir = zenPath('ZenPacks')
                cmd = ('python setup.py develop -u '
                        '--site-dirs=%s ' % zenPackDir +
                        '-d %s' % zenPackDir)
                p = subprocess.Popen(cmd,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    shell=True,
                                    cwd=zp.eggPath())
                p.wait()
                errors = p.stderr.read()
                if errors:
                    raise ZenPackException(errors)
            else:
                # Do we need to call easy_install -m here?  It causes problems
                # because it tries to install deps.  However, we might be leaving
                # around lines in easy-install.pth otherwise.
                pass
            if deleteFiles:
                eggLink = './%s' % zp.eggName()
                p = subprocess.Popen(
                    'rm -rf %s' % zp.eggPath(),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    shell=True)
                p.wait()
                # Looks like maybe this is not needed.  at least some of the 
                # time the easy-install.pth file is removed by setuptools
                #CleanupEasyInstallPth(eggLink)
        cleanupSkins(dmd)
        transaction.commit()
    except:
        if sendEvent:
            ZPEvent(dmd, 4, 'Error removing ZenPack %s' % packName,
                '%s: %s' % sys.exc_info()[:2])
        raise
    if sendEvent:
        ZPEvent(dmd, 2, 'Removed ZenPack %s' % packName)


def CanRemoveZenPacks(dmd, packNames):
    """
    Returns a tuple of (canRemove, otherDependents)
    canRemove is True if the listed zenPacks have no dependents not also
    listed in packNames, False otherwise.
    otherDependents is a list of zenpack names not in packNames that
    depend on one or more of the packs in packNames.
    """
    unhappy = set()
    for name in packNames:
        deps = GetDependents(dmd, name)
        unhappy.update(set([dep for dep in deps if dep not in packNames]))
    return (not unhappy and True or False, list(unhappy))


def CleanupEasyInstallPth(eggLink):
    # Remove the path from easy-install.pth
    easyPth = zenPath('ZenPacks', 'easy-install.pth')
    f = open(easyPth, 'r')
    newLines = [l for l in f if l.strip() != eggLink]
    f.close()
    f = open(easyPth, 'w')
    f.writelines(newLines)
    f.close()


def GetDependents(dmd, packName):
    """
    Return a list of installed ZenPack ids that list packName as a dependency
    """
    return [zp.id for zp in dmd.ZenPackManager.packs()
                if zp.id != packName and zp.dependencies.has_key(packName)]


########################################
#   __main__, dispatching, etc
########################################


def ZPEvent(dmd, severity, summary, message=None):
    """
    Send an event to Zenoss.
    """
    dmd.ZenEventManager.sendEvent(dict(
        device=FQDN,
        eventClass='/Unknown',
        severity=severity,
        summary=summary,
        message=message))


class ZenPackCmd(ZenScriptBase):
    """
    Utilities for creating, installing, removing ZenPacks.

    NOTE: Users will probably invoke zenpack from the command line, which
    runs zenpack.py rather than this file.  zenpack.py calls functions
    in this module when it detects that new-style (egg) ZenPacks are involved.
    The plan is that once support for old-style (non-egg) ZenPacks is dropped
    zenpack.py can go away and this will take its place.  Until then this
    script can be invoked directly via the zenpackcmd script if desired.
    Invoking this script directly has the benefit of slightly better
    progress/status output to stdout.
    """

    def run(self):
        """
        Execute the user's request.
        """

        self.connect()
        def PrintInstalled(installed):
            if installed:
                print('Installed ZenPack%s: %s' % (
                        len(installed) > 1 and 's' or '',
                        ', '.join([i.id for i in installed])))
            else:
                print('No ZenPacks installed.')

        if not getattr(self.dmd, 'ZenPackManager', None):
            raise ZenPackNeedMigrateException('Your Zenoss database appears'
                ' to be out of date. Try running zenmigrate to update.')
        if self.options.eggPath:
            installed = InstallEggAndZenPack(
                                self.dmd, self.options.eggPath,
                                link=self.options.link,
                                filesOnly=self.options.filesOnly)
            PrintInstalled(installed)
        elif self.options.fetch:
            installed = FetchAndInstallZenPack(self.dmd, self.options.fetch)
            PrintInstalled(installed)
        elif self.options.upload:
            return UploadZenPack(self.dmd, self.options.upload,
                                    self.options.znetProject,
                                    self.options.uploadDesc,
                                    self.options.znetUser,
                                    self.options.znetPass)
        elif self.options.removePackName:
            try:
                RemoveZenPack(self.dmd, self.options.removePackName)
                print('Removed ZenPack: %s' % self.options.removePackName)
            except ZenPackNotFoundException, e:
                sys.stderr.write(str(e) + '\n')
        elif self.options.list:
            self.list()


    def buildOptions(self):
        self.parser.add_option('--install',
                               dest='eggPath',
                               default=None,
                               help="name of the pack to install")
#        self.parser.add_option('--fetch',
#                               dest='fetch',
#                               default=None,
#                               help='Name of ZenPack to retrieve from '
#                                    'Zenoss.net and install.')
#        self.parser.add_option('--fetch-vers',
#                               dest='fetchVers',
#                               default=None,
#                               help='Use with --fetch to specify a version'
#                                    ' for the ZenPack to download and install.')
#        self.parser.add_option('--znet-user',
#                               dest='znetUser',
#                               default=None,
#                               help='Use with --fetch or --upload to specify'
#                                    ' your Zenoss.net username.')
#        self.parser.add_option('--znet-pass',
#                               dest='znetPass',
#                               default=None,
#                               help='Use with --fetch or --upload to specify'
#                                    ' your Zenoss.net password.')
#        self.parser.add_option('--upload',
#                               dest='upload',
#                               default=None,
#                               help='Name of ZenPack to upload to '
#                                    'Zenoss.net')
#        self.parser.add_option('--znet-project',
#                               dest='znetProject',
#                               default=None,
#                               help='Use with --upload to specify'
#                                    ' which Zenoss.net project to create'
#                                    ' a release on.')
#        self.parser.add_option('--upload-desc',
#                               dest='uploadDesc',
#                               default=None,
#                               help='Use with --upload to provide'
#                                    ' a description for the new release.')
        self.parser.add_option('--link',
                               dest='link',
                               action='store_true',
                               default=False,
                               help='Install the ZenPack in its current '
                                'location, do not copy to $ZENHOME/ZenPacks. '
                                'Also mark ZenPack as editable. '
                                'This only works with source directories '
                                'containing setup.py files, not '
                                'egg files.')
        self.parser.add_option('--remove',
                               dest='removePackName',
                               default=None,
                               help="name of the pack to remove")
        self.parser.add_option('--leave-objects',
                               dest='leaveObjects',
                               default=False,
                               action='store_true',
                               help="When specified with --remove then objects"
                                    ' provided by the ZenPack and those'
                                    ' depending on the ZenPack are not deleted.'
                                    ' This may result in broken objects in your'
                                    ' database unless the ZenPack is'
                                    ' reinstalled.')
        self.parser.add_option('--files-only',
                               dest='filesOnly',
                               action="store_true",
                               default=False,
                               help='install onto filesystem but not into '
                                        'zenoss')
        ZenScriptBase.buildOptions(self)


if __name__ == '__main__':
    try:
        zp = ZenPackCmd()
        zp.run()
    except ZenPackException, e:
        sys.stderr.write('%s\n' % str(e))
        sys.exit(-1)
