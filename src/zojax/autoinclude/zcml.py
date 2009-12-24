##############################################################################
#
# Copyright (c) 2009 Zope Foundation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################
"""

$Id$
"""
import os.path
from zope import schema
from zope.interface import Interface
from zope.dottedname.resolve import resolve
from zope.configuration.fields import GlobalObject, Tokens
from zope.configuration.xmlconfig import exclude, include, includeOverrides

from pkg_resources import get_provider, UnknownExtra
from utils import ZCMLInfo, DistributionManager, distributionForPackage


class IIncludeAllDependenciesDirective(Interface):
    """Auto-include any ZCML in the dependencies of this package."""

    package = GlobalObject(
        title = u"Package to auto-include for",
        description = u"""Auto-include all dependencies of this package.""",
        required = True)

    extras = Tokens(
        title = u'Extras',
        value_type = schema.TextLine(),
        required = False)

    exclude = Tokens(
        title = u'Exclude packages',
        value_type = schema.TextLine(),
        required = False)


def includeAllDependenciesDirective(_context, package, exclude=(), extras=()):
    dist = distributionForPackage(package)

    info = ZCMLInfo(['configure.zcml', 'meta.zcml',
                     'overrides.zcml', 'exclude.zcml'])
    DependencyFinder(dist).includableInfo(
        ['configure.zcml', 'meta.zcml', 'overrides.zcml', 'exclude.zcml'],
        info, None, exclude, extras)

    includeZCMLGroup(_context, info, 'meta.zcml')
    includeZCMLGroup(_context, info, 'exclude.zcml')

    # fix zope.app.xxx dependencies
    data = info['configure.zcml']
    if 'zope.app.appsetup' in data:
        data.remove('zope.app.appsetup')
        data.insert(0, 'zope.app.appsetup')

    if 'zope.app.zcmlfiles' in data:
        includable_package = resolve('zope.app.zcmlfiles')
        include(_context, 'menus.zcml', includable_package)

    includeZCMLGroup(_context, info, 'configure.zcml')
    includeZCMLGroup(_context, info, 'overrides.zcml', True)


def includeZCMLGroup(_context, info, filename, override=False):
    includable_zcml = info[filename]

    zcml_context = repr(_context.info)

    for dotted_name in includable_zcml:
        includable_package = resolve(dotted_name)
        if override:
            includeOverrides(_context, filename, includable_package)
        else:
            include(_context, filename, includable_package)


class DependencyFinder(DistributionManager):

    def includeReqs(self, reqs, zcml_to_look_for, result, seen, exclude):
        for req in reqs:
            pkg = req.project_name
            if pkg == 'setuptools' or pkg in exclude:
                continue

            if req.extras:
                for extra in req.extras:
                    if (pkg, extra) in seen:
                        continue

                    try:
                        dist = get_provider(req)
                    except:
                        seen.add(pkg)
                        continue

                    DependencyFinder(dist).includableInfo(
                        zcml_to_look_for, result, seen, exclude, (extra,))
            else:
                if pkg in seen:
                    continue

                try:
                    dist = get_provider(req)
                except:
                    seen.add(pkg)
                    continue

                DependencyFinder(dist).includableInfo(
                    zcml_to_look_for, result, seen, exclude)


    def includableInfo(self, zcml_to_look_for, result,
                       seen=None, exclude=(), extras=()):
        if seen is None:
            seen = set()

        seen.add(self.context.project_name)

        self.includeReqs(self.context.requires(), zcml_to_look_for, result, seen, exclude)

        for dotted_name in self.dottedNames():
            module = resolve(dotted_name)
            for candidate in zcml_to_look_for:
                candidate_path = os.path.join(
                    os.path.dirname(module.__file__), candidate)
                if os.path.isfile(candidate_path):
                    if dotted_name not in result[candidate]:
                        result[candidate].append(dotted_name)

        for extra in extras:
            seen.add((self.context.project_name, extra))

            try:
                reqs = self.context.requires(extras=(extra,))
            except UnknownExtra:
                return

            if reqs:
                self.includeReqs(reqs, zcml_to_look_for, result, seen, exclude)
