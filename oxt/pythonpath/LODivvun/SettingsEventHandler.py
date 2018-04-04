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

import libdivvun

def __getprop__(name, value):
	p, p.Name, p.Value = __property__(), name, value
	return p

def partition(lst, pred):
	good, bad = [], []
	for x in lst:
		good.append(x) if pred(x) else bad.append(x)
	return good, bad

class SettingsEventHandler(unohelper.Base, XServiceInfo, XContainerWindowEventHandler):

	def __init__(self, ctx, *args):
		print("SettingsEventHandler.__init__")
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
		hyphWordPartsValue = False
		hyphUnknownWordsValue = True
		try:
			hyphWordPartsValue = PropertyManager.getInstance().readFromRegistry("/no.divvun.gramcheck.Config/hyphenator",  "hyphWordParts")
			hyphUnknownWordsValue = PropertyManager.getInstance().readFromRegistry("/no.divvun.gramcheck.Config/hyphenator", "hyphUnknownWords")
		except UnknownPropertyException as e:
			logging.exception("SettingsEventHandler: UnknownPropertyException", e)
			return
		logging.debug("hyphWordParts = " + str(hyphWordPartsValue))
		hyphWordParts = window.getControl("hyphWordParts")

		hyphWordPartsProps = hyphWordParts.getModel()
		hyphWordPartsProps.setPropertyValue("State", 1 if hyphWordPartsValue else 0)

		hyphUnknownWords = window.getControl("hyphUnknownWords")
		hyphUnknownWordsProps = hyphUnknownWords.getModel()
		hyphUnknownWordsProps.setPropertyValue("State", 1 if hyphUnknownWordsValue else 0)

		self.__initVariantDropdown(window)
		self.__initGcDropdown(window)

	def __saveOptionsFromWindowToRegistry(self, window):
		logging.debug("SettingsEventHandler.__saveOptionsFromWindowToRegistry")

		hyphWordParts = window.getControl("hyphWordParts")
		hyphWordPartsProps = hyphWordParts.getModel()
		hyphWordPartsValue = hyphWordPartsProps.getPropertyValue("State") # 0 = unchecked, 1 = checked

		hyphUnknownWords = window.getControl("hyphUnknownWords")
		hyphUnknownWordsProps = hyphUnknownWords.getModel()
		hyphUnknownWordsValue = hyphUnknownWordsProps.getPropertyValue("State") # 0 = unchecked, 1 = checked

		rootView = PropertyManager.getRegistryProperties("/no.divvun.gramcheck.Config/hyphenator")
		rootView.setHierarchicalPropertyValue("hyphWordParts", hyphWordPartsValue == 1)
		rootView.setHierarchicalPropertyValue("hyphUnknownWords", hyphUnknownWordsValue == 1)
		rootView.commitChanges()

		# dictionary variant
		variantValue = self.__getSelectedVariant(window)
		rootView = PropertyManager.getRegistryProperties("/no.divvun.gramcheck.Config/dictionary")
		rootView.setHierarchicalPropertyValue("variant", variantValue)
		rootView.commitChanges()

		# dictionary gcsetting
		gcsettingValue = self.__getSelectedGcsetting(window)
		rootView = PropertyManager.getRegistryProperties("/no.divvun.gramcheck.Config/dictionary")
		rootView.setHierarchicalPropertyValue("gcsetting", gcsettingValue)
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


	def __initGcDropdown(self, windowContainer):
		provider = uno.getComponentContext().getValueByName("/singletons/com.sun.star.configuration.theDefaultProvider")
		l10n = provider.createInstanceWithArguments("com.sun.star.configuration.ConfigurationAccess",
							    (__getprop__("nodepath", "/org.openoffice.Setup/L10N"),))
		uilocale_raw = l10n.getByName("ooLocale") + '-'  # handle missing Country of locale 'eo'
		uilocale = Locale(uilocale_raw.split('-')[0], uilocale_raw.split('-')[1], '')

		logging.info("KBU: uilocale {}".format(uilocale))
		toggleIds = {}
		pool = DivvunHandlePool.getInstance()
		handles = pool.getOpenHandles()
		for checklang, checker in handles.items():
			prefs = libdivvun.prefs_bytes(checker)
			logging.info("KBU: prefs of checker for lang {} has pref l18n langs {}".format(checklang, prefs.keys()))
			# First add explanations from the other
			# languages, then those of the UI language, so
			# the UI language explanations are preferred:
			uilang, otherlangs = partition(prefs.items(), lambda lp: lp[0] == uilocale.Language)
			toggleIds.update(otherlangs)
			toggleIds.update(uilang)
		logging.info("KBU: prefs of checker for lang {} has toggleIds {}".format(checklang, toggleIds))
		variantDropdown = windowContainer.getControl("gcmenulist")
		variantProps = variantDropdown.getModel()

		gcsettings = ["do thing", "don't do thing"]
		uno.invoke(variantProps, "setPropertyValue", ("StringItemList", uno.Any("[]string", tuple(gcsettings))))

		# read selected dictionary variant from registry
		registryVariantValue = "do thing"
		try:
			registryVariantValue = PropertyManager.getInstance().readFromRegistry("/no.divvun.gramcheck.Config/dictionary", "gcsetting")
		except UnknownPropertyException as e:
			logging.exception(e)
			return
		registryVariantValue = registryVariantValue + ": "
		selectedValues = [0]
		for i, dVariant in enumerate(gcsettings):
			if dVariant.startswith(registryVariantValue):
				selectedValues[0] = i;
				break;

		# set the selected item in the dropdown list
		uno.invoke(variantProps, "setPropertyValue", ("SelectedItems", uno.Any("[]short", tuple(selectedValues))))

	def __initAvailableVariants(self):
		# dicts = libdivvun.listDicts(DivvunHandlePool.getInstance().getDictionaryPath())
		dicts = []
		self.__dictionaryVariantList = ["kbu: TODO"]
		for vDict in dicts:
			dictName = vDict.variant + ": " + vDict.description
			self.__dictionaryVariantList.append(dictName)

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
		gcsettingDropdown = windowContainer.getControl("gcmenulist")
		gcsettingProps = gcsettingDropdown.getModel()

		# get all values
		stringListValue = gcsettingProps.getPropertyValue("StringItemList")

		# get the selected item index
		selectedValues = gcsettingProps.getPropertyValue("SelectedItems")

		# parse the gcsetting id from the string
		selectedValue = stringListValue[selectedValues[0]]
		if ":" in selectedValue:
			return selectedValue[0:selectedValue.find(":")]
		logging.error("Failed to get the selected gcsetting, returning default")
		return "standard"


SettingsEventHandler.IMPLEMENTATION_NAME = "no.divvun.gramcheck.SettingsEventHandlerImplementation"
SettingsEventHandler.SUPPORTED_SERVICE_NAMES = ("no.divvun.gramcheck.SettingsEventHandlerService",)
