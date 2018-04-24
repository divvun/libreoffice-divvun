# Libreoffice-divvun: Linguistic extension for LibreOffice
# Copyright (C) 2015 Harri Pitkänen <hatapitk@iki.fi>
#
# This Source Code Form is subject to the terms of the Mozilla Public License,
# v. 2.0. If a copy of the MPL was not distributed with this file, You can
# obtain one at http://mozilla.org/MPL/2.0/.
#
# Alternatively, the contents of this file may be used under the terms of
# the GNU General Public License Version 3 or later (the "GPL"), in which
# case the provisions of the GPL are applicable instead of those above.

import pydoc			# DEBUG

import unohelper
import logging
import uno
from com.sun.star.lang import XServiceInfo
from com.sun.star.awt import XContainerWindowEventHandler
from com.sun.star.beans import UnknownPropertyException
from com.sun.star.beans import PropertyValue as __property__
from com.sun.star.lang import Locale
from com.sun.star.awt import XActionListener

from LODivvun.PropertyManager import PropertyManager
from LODivvun.DivvunHandlePool import DivvunHandlePool
import libdivvun

try:
	from typing import TypeVar, Set, List, Tuple, Dict, Callable, Any     # flake8: noqa
	T = TypeVar('T')
except ImportError:
	pass


def __getprop__(name, value):
	p, p.Name, p.Value = __property__(), name, value
	return p


def partition(lst, pred):	# type: (List[T], Callable[[T], bool]) -> Tuple[List[T], List[T]]
	good, bad = [], []
	for x in lst:
		if pred(x):
			good.append(x)
		else:
			bad.append(x)
	return good, bad


def getUILocale():		# type: () -> Locale
	provider = uno.getComponentContext().getValueByName("/singletons/com.sun.star.configuration.theDefaultProvider")
	l10n = provider.createInstanceWithArguments("com.sun.star.configuration.ConfigurationAccess",
						    (__getprop__("nodepath", "/org.openoffice.Setup/L10N"),))
	uilocaleRaw = l10n.getByName("ooLocale") + '-'  # handle missing Country of locale 'eo'
	return Locale(uilocaleRaw.split('-')[0], uilocaleRaw.split('-')[1], '')


def getToggleIds():		# type: () -> Dict[str, str]
	"""Return the toggleIds of currently opened checker handles.

Don't cache this – the result may change if more handles (checkers)
are loaded (and if UI locale changes, though that's not too bad)

	"""
	toggleIds = {}		# type: Dict[str, str]
	uilocale = getUILocale()
	logging.info("KBU: uilocale {}".format(uilocale))
	pool = DivvunHandlePool.getInstance()
	handles = pool.getOpenHandles()
	for checklang, checker in handles.items():
		prefs = libdivvun.prefs_bytes(checker)
		logging.info("KBU: prefs of checker for lang {} has pref l18n langs {}".format(checklang, prefs.keys()))
		# First add explanations from the other languages,
		# then those of the checker, then the UI language, so
		# the UI and checker language explanations are
		# preferred:
		p_uilang, p_notui = partition(prefs.items(), lambda lp: lp[0] == uilocale.Language)
		p_checklang, p_notcheckui = partition(p_notui, lambda lp: lp[0] == checklang)
		logging.info("KBU: prefs of checker for lang {} has p_uilang {}".format(checklang, p_uilang))
		logging.info("KBU: prefs of checker for lang {} has p_checklang {}".format(checklang, p_checklang))
		logging.info("KBU: prefs of checker for lang {} has p_notcheckui {}".format(checklang, p_notcheckui))
		for _l, p in p_notcheckui:
			toggleIds.update(p.toggleIds)
		for _l, p in p_checklang:
			toggleIds.update(p.toggleIds)
		for _l, p in p_uilang:
			toggleIds.update(p.toggleIds)
	logging.info("KBU: prefs of checker for lang {} has toggleIds {}".format(checklang, toggleIds))
	# Remove empty ones, just confusing:
	return { k:v
		 for k,v in toggleIds.items()
		 if k.strip() != "" and v.strip() != "" }


def readIgnoredRules():		# type: () -> Set[str]
	"""Read ignored rule identifiers from registry"""
	try:
		registryRaw = PropertyManager.getInstance().readFromRegistry("/no.divvun.gramcheck.Config/dictionary", "gcignored")
		logging.debug("KBU: Read gcignored registryRaw {}".format(registryRaw))
		return set(registryRaw.split())
	except UnknownPropertyException as e:
		logging.exception(e)
		return set()


def saveIgnoredRules(ignoredRules):  # type: (Set[str]) -> None
	"""Save ignored rule identifiers to registry"""
	gcsettingTids = " ".join(ignoredRules)
	rootView = PropertyManager.getRegistryProperties("/no.divvun.gramcheck.Config/dictionary")
	rootView.setHierarchicalPropertyValue("gcignored", gcsettingTids)
	logging.debug("KBU: gcignored registry set to {}".format(gcsettingTids))
	rootView.commitChanges()

def getListSelections(listM):	# type: (Any) -> Dict[int, str]
	stringListValue = listM.getPropertyValue("StringItemList")
	selectedValues = listM.getPropertyValue("SelectedItems")
	logging.info("KBU: selectedValues {}".format(list((i, stringListValue[i]) for i in selectedValues)))
	return {i: stringListValue[i]
		for i in selectedValues}

def getListValues(listM):	# type: (Any) -> Dict[int, str]
	stringListValue = listM.getPropertyValue("StringItemList")
	return dict(enumerate(stringListValue))


class SettingsEventHandler(unohelper.Base, XServiceInfo, XContainerWindowEventHandler):

	def __init__(self, ctx, *args):
		print("SettingsEventHandler.__init__")
		self.__initToggleIds()

	def __initToggleIds(self):
		# Since listbox only stores msg, not error id, we set
		# this on init here, expecting user to restart LO if
		# they install a new language pack
		self.__toggleIds = getToggleIds()

	# From XServiceInfo
	def getImplementationName(self):
		return SettingsEventHandler.IMPLEMENTATION_NAME

	def supportsService(self, serviceName):
		return serviceName in self.getSupportedServiceNames()

	def getSupportedServiceNames(self):
		return SettingsEventHandler.SUPPORTED_SERVICE_NAMES

	# From XContainerWindowEventHandler
	def callHandlerMethod(self, xWindow, eventObject, methodName):
		if methodName != "external_event":
			return False
		if eventObject == "ok":
			self.__saveOptionsFromWindowToRegistry(xWindow)
			PropertyManager.getInstance().reloadDivvunSettings()
			return True
		if eventObject == "back" or eventObject == "initialize":
			self.__initOptionsWindowFromRegistry(xWindow)
			return True
		return False

	def getSupportedMethodNames(self):
		return ("external_event",)

	def __initOptionsWindowFromRegistry(self, window):
		logging.debug("initOptionsWindowFromRegistry()");
		self.__initGcDropdown(window)

	def __saveOptionsFromWindowToRegistry(self, windowC):
		logging.debug("SettingsEventHandler.__saveOptionsFromWindowToRegistry")
		ignoreM = windowC.getControl("toggleIdsIgnore").getModel()
		ignoreMsgs =  getListValues(ignoreM).values()
		ignoredRules = {tid
				for (tid,msg) in self.__toggleIds.items()
				if msg in ignoreMsgs}
		saveIgnoredRules(ignoredRules)

	def __updateToggleIds(self, registryIgnored):  # type: (Set[str]) -> None
		"""Add any ignored rules from registry with the rule identifier as message.

		Sometimes the registry will have saved ignored rules
		which are not returned from getToggleIds (e.g. if
		errors.xml's did not describe all the possible rule
		ids that the checker can create).

		"""
		existingTids = self.__toggleIds.keys()
		ignoredButNoMsg = registryIgnored - existingTids
		toAdd  = { tid: tid for tid in ignoredButNoMsg}
		self.__toggleIds.update(toAdd)

	def __initGcDropdown(self, windowC):
		ignoreM  = windowC.getControl("toggleIdsIgnore").getModel()
		includeM = windowC.getControl("toggleIdsInclude").getModel()
		registryIgnored = readIgnoredRules()
		self.__updateToggleIds(registryIgnored)
		# TODO: Some of these errors.xml messages have
		# non-unique messages. Since there's no way for the
		# user to differentiate them, we can't really do
		# anything except conflate them – unless we append the
		# tid to make them unique?
		ignoreMsgs  = set(msg
				  for (tid, msg) in self.__toggleIds.items()
				  if tid in registryIgnored)
		includeMsgs = set(msg
				  for (tid, msg) in self.__toggleIds.items()
				  if tid not in registryIgnored)
		uno.invoke(ignoreM, "setPropertyValue", ("StringItemList", uno.Any("[]string", tuple(sorted(ignoreMsgs)))))
		uno.invoke(includeM, "setPropertyValue", ("StringItemList", uno.Any("[]string", tuple(sorted(includeMsgs)))))
		# Enable buttons:
		windowC.getControl("addIgnore").addActionListener(IgnoreActionListener(ignoreM, includeM))
		windowC.getControl("addInclude").addActionListener(IncludeActionListener(ignoreM, includeM))

	# def __initGcDropdownFailedAttempts(self, windowC):
		# windowM = windowC.getModel()
		# logging.info("KBU: windowM:")
		# logging.info(windowM)
		# logging.info("KBU: windowM.getTypes:")
		# logging.info(windowM.getTypes())
		# logging.info("KBU: windowM.getImplementationId:")
		# logging.info(windowM.getImplementationId())
		# logging.info("KBU: windowM.getSupportedServiceNames:")
		# logging.info(windowM.getSupportedServiceNames())
		# logging.info("KBU: /windowM")

		# boxC = windowC.getControl("toggleIds")
		# boxM = boxC.getModel()
		# logging.info("KBU: boxM:")
		# logging.info(boxM)
		# logging.info("KBU: boxM.getTypes:")
		# logging.info("KBU: boxM.getTypes: {}".format(boxM.getTypes()))
		# logging.info("KBU: boxM.getImplementationId:")
		# logging.info(boxM.getImplementationId())
		# logging.info("KBU: boxM.getSupportedServiceNames:")
		# logging.info(boxM.getSupportedServiceNames())
		# logging.info("KBU: /boxM")

		# toggleMsgs = tuple([msg for _tid,msg in self.__toggleIds])
		# uno.invoke(boxM, "setPropertyValue", ("StringItemList", uno.Any("[]string", toggleMsgs)))

		# ctx = uno.getComponentContext()
		# cb1 = ctx.ServiceManager.createInstanceWithContext("com.sun.star.form.component.CheckBox", ctx)
		# cb1.Label = "KBU: some label"
		# cb1.State = 1;
		# logging.info("KBU cb1: {}".format(cb1))
		# # TODO: Why does this not work?
		# # boxM.insertByName("myCb1", cb1)
		# windowM.insertByName("myCb1b", cb1)

		# TODO: Could do this, but need to figure out how to position them, and scroll correctly
		# for i, (tid, msg) in enumerate(list(getToggleIds().items())[:10]):
		# 	cb = ctx.ServiceManager.createInstanceWithContext("com.sun.star.form.component.CheckBox", ctx)
		# 	cb.Label = msg;
		# 	cb.State = 1;
		# 	cb.Name = tid;
		# 	wname = "toggleId-"+tid;
		# 	windowM.insertByName(wname, cb)
		# 	# logging.info("KBU: Control: {}".format(windowC.getControl(wname).getModel().PositionX))


SettingsEventHandler.IMPLEMENTATION_NAME = "no.divvun.gramcheck.SettingsEventHandlerImplementation"
SettingsEventHandler.SUPPORTED_SERVICE_NAMES = ("no.divvun.gramcheck.SettingsEventHandlerService",)

class IgnoreActionListener(unohelper.Base, XActionListener):
	def __init__(self, ignoreM, includeM):
		self.ignoreM = ignoreM
		self.includeM = includeM
		logging.info("KBU: init IgnoreActionListener")
	def disposing(self, ev):
		logging.info("KBU: dispose IgnoreActionListener")
	def actionPerformed(self, ev):
		logging.info("KBU: actionPerformed IgnoreActionListener")
		includeSelection = getListSelections(self.includeM).values()  # to be ignored
		ignoreMsgs =  set(includeSelection).union(getListValues(self.ignoreM).values())
		includeMsgs = { msg
				for msg in getListValues(self.includeM).values()
				if msg not in includeSelection }
		logging.info("KBU: ignoreMsgs {}".format(ignoreMsgs))
		logging.info("KBU: tuple ignoreMsgs {}".format(tuple(ignoreMsgs)))
		logging.info("KBU: includeMsgs {}".format(includeMsgs))
		logging.info("KBU: tuple includeMsgs {}".format(tuple(includeMsgs)))
		uno.invoke(self.ignoreM, "setPropertyValue", ("StringItemList", uno.Any("[]string", tuple(sorted(ignoreMsgs)))))
		uno.invoke(self.includeM, "setPropertyValue", ("StringItemList", uno.Any("[]string", tuple(sorted(includeMsgs)))))

class IncludeActionListener(unohelper.Base, XActionListener):
	def __init__(self, ignoreM, includeM):
		self.ignoreM = ignoreM
		self.includeM = includeM
		logging.info("KBU: init IncludeActionListener")
	def disposing(self, ev):
		logging.info("KBU: dispose IncludeActionListener")
	def actionPerformed(self, ev):
		logging.info("KBU: actionPerformed IncludeActionListener")
		ignoreSelection = getListSelections(self.ignoreM).values()  # to be included
		ignoreMsgs = { msg
			       for msg in getListValues(self.ignoreM).values()
			       if msg not in ignoreSelection }
		includeMsgs = set(ignoreSelection).union(getListValues(self.includeM).values())
		uno.invoke(self.ignoreM, "setPropertyValue", ("StringItemList", uno.Any("[]string", tuple(sorted(ignoreMsgs)))))
		uno.invoke(self.includeM, "setPropertyValue", ("StringItemList", uno.Any("[]string", tuple(sorted(includeMsgs)))))
