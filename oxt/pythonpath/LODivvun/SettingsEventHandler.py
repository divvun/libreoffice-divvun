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
from LODivvun.PropertyManager import PropertyManager
from LODivvun.DivvunHandlePool import DivvunHandlePool

try:
    from typing import Set, List, Tuple, Dict, Any     # flake8: noqa
except ImportError:
    pass

import libdivvun


def __getprop__(name, value):
	p, p.Name, p.Value = __property__(), name, value
	return p


def partition(lst, pred):
	good, bad = [], []
	for x in lst:
		if pred(x):
			good.append(x)
		else:
			bad.append(x)
	return good, bad


def getUILocale():
	provider = uno.getComponentContext().getValueByName("/singletons/com.sun.star.configuration.theDefaultProvider")
	l10n = provider.createInstanceWithArguments("com.sun.star.configuration.ConfigurationAccess",
						    (__getprop__("nodepath", "/org.openoffice.Setup/L10N"),))
	uilocaleRaw = l10n.getByName("ooLocale") + '-'  # handle missing Country of locale 'eo'
	return Locale(uilocaleRaw.split('-')[0], uilocaleRaw.split('-')[1], '')


def getToggleIds():
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
		# First add explanations from the other
		# languages, then those of the UI language, so
		# the UI language explanations are preferred:
		uilang, otherlangs = partition(prefs.items(), lambda lp: lp[0] == uilocale.Language)
		logging.info("KBU: prefs of checker for lang {} has uilang {}".format(checklang, uilang))
		logging.info("KBU: prefs of checker for lang {} has otherlangs {}".format(checklang, otherlangs))
		for _l, p in otherlangs:
			toggleIds.update(p.toggleIds)
		for _l, p in uilang:
			toggleIds.update(p.toggleIds)
	logging.info("KBU: prefs of checker for lang {} has toggleIds {}".format(checklang, toggleIds))
	return toggleIds


class SettingsEventHandler(unohelper.Base, XServiceInfo, XContainerWindowEventHandler):

	def __init__(self, ctx, *args):
		print("SettingsEventHandler.__init__")
		# Since listbox only stores msg, not error id, we set
		# this on init here, expecting user to restart LO if they
		# install a new language pack
		self.__toggleIds = list(getToggleIds().items())	 # type: List[Tuple[str, str]]
		self.__idxToToggleId = dict(enumerate(self.__toggleIds))  # type: Dict[int, Tuple[str, str]]
		self.__dictionaryVariantList = ["standard: standard dictionary"]

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

	def __saveOptionsFromWindowToRegistry(self, window):
		logging.debug("SettingsEventHandler.__saveOptionsFromWindowToRegistry")
		gcsettingValue = set(idx for idx, _msg in self.__getSelectedGcsetting(window))
		gcsettingTids = " ".join(tid
					 for i,(tid,_msg)
					 in self.__idxToToggleId.items()
					 if i in gcsettingValue)
		rootView = PropertyManager.getRegistryProperties("/no.divvun.gramcheck.Config/dictionary")
		rootView.setHierarchicalPropertyValue("gcignored", gcsettingTids)
		logging.debug("KBU: gcignored registry set to {}".format(gcsettingTids))
		rootView.commitChanges()

	def __initVariantDropdown(self, windowContainer):
		variantDropdown = windowContainer.getControl("variant")
		variantProps = variantDropdown.getModel()

		# populate dropdown list with available variants
		self.__initAvailableVariants()
		uno.invoke(variantProps, "setPropertyValue", ("StringItemList", uno.Any("[]string", tuple(self.__dictionaryVariantList))))

		# read selected dictionary variant from registry
		registryVariantValue = "standard"
		try:
			registryVariantValue = PropertyManager.getInstance().readFromRegistry("/no.divvun.gramcheck.Config/dictionary", "variant")
		except UnknownPropertyException as e:
			logging.exception(e)
			return
		registryVariantValue = registryVariantValue + ": "
		selectedValues = [0]
		for i, dVariant in enumerate(self.__dictionaryVariantList):
			if dVariant.startswith(registryVariantValue):
				selectedValues[0] = i;
				break;

		# set the selected item in the dropdown list
		uno.invoke(variantProps, "setPropertyValue", ("SelectedItems", uno.Any("[]short", tuple(selectedValues))))


	def __initGcDropdown(self, windowC):
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

		boxC = windowC.getControl("toggleIds")
		boxM = boxC.getModel()
		# logging.info("KBU: boxM:")
		# logging.info(boxM)
		# logging.info("KBU: boxM.getTypes:")
		# logging.info("KBU: boxM.getTypes: {}".format(boxM.getTypes()))
		# logging.info("KBU: boxM.getImplementationId:")
		# logging.info(boxM.getImplementationId())
		# logging.info("KBU: boxM.getSupportedServiceNames:")
		# logging.info(boxM.getSupportedServiceNames())
		# logging.info("KBU: /boxM")

		boxC = windowC.getControl("toggleIds")
		boxM = boxC.getModel()
		toggleMsgs = tuple([msg for _tid,msg in self.__toggleIds])
		uno.invoke(boxM, "setPropertyValue", ("StringItemList", uno.Any("[]string", toggleMsgs)))

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

		# read selected dictionary variant from registry
		registryIgnored = set()	 # type: Set[str]
		try:
			registryRaw = PropertyManager.getInstance().readFromRegistry("/no.divvun.gramcheck.Config/dictionary", "gcignored")

			logging.debug("KBU: gcignored registryRaw {}".format(registryRaw))
			registryIgnored = set(registryRaw.split())
		except UnknownPropertyException as e:
			logging.exception(e)
			return
		selectedValues = set(i
				     for i,(tid,_msg)
				     in self.__idxToToggleId.items()
				     if tid in registryIgnored)
		uno.invoke(boxM, "setPropertyValue", ("SelectedItems", uno.Any("[]short", tuple(selectedValues))))

	def __initAvailableVariants(self):
		# dicts = libdivvun.listDicts(DivvunHandlePool.getInstance().getDictionaryPath())
		# dicts = []
		self.__dictionaryVariantList = ["kbu: TODO"]
		# for vDict in dicts:
			# dictName = vDict.variant + ": " + vDict.description
			# self.__dictionaryVariantList.append(dictName)

	def __getSelectedVariant(self, windowContainer):
		variantDropdown = windowContainer.getControl("variant")
		variantProps = variantDropdown.getModel()

		# get all values
		stringListValue = variantProps.getPropertyValue("StringItemList")

		# get the selected item index
		selectedValues = variantProps.getPropertyValue("SelectedItems")

		# parse the variant id from the string
		selectedValue = stringListValue[selectedValues[0]]
		if ":" in selectedValue:
			return selectedValue[0:selectedValue.find(":")]
		logging.error("Failed to get the selected variant, returning default")
		return "standard"


	def __getSelectedGcsetting(self, windowContainer):
		gcsettingDropdown = windowContainer.getControl("toggleIds")
		gcsettingProps = gcsettingDropdown.getModel()
		stringListValue = gcsettingProps.getPropertyValue("StringItemList")
		selectedValues = gcsettingProps.getPropertyValue("SelectedItems")
		logging.info("KBU: selectedValues {}".format(list((i, stringListValue[i]) for i in selectedValues)))
		return list((i, stringListValue[i]) for i in selectedValues)


SettingsEventHandler.IMPLEMENTATION_NAME = "no.divvun.gramcheck.SettingsEventHandlerImplementation"
SettingsEventHandler.SUPPORTED_SERVICE_NAMES = ("no.divvun.gramcheck.SettingsEventHandlerService",)