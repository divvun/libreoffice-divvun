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

import logging
import unohelper 		# type:ignore
from com.sun.star.linguistic2 import XHyphenator, XLinguServiceEventBroadcaster	 # type:ignore
from com.sun.star.lang import XServiceInfo, XInitialization, XServiceDisplayName  # type:ignore
from LODivvun.DivvunHandlePool import DivvunHandlePool
from LODivvun.HyphenatedWord import HyphenatedWord
from LODivvun.PossibleHyphens import PossibleHyphens
from LODivvun.PropertyManager import PropertyManager

class Hyphenator(unohelper.Base, XServiceInfo, XHyphenator, XLinguServiceEventBroadcaster, XInitialization, XServiceDisplayName):

	def __init__(self, ctx, *args):
		logging.debug("Hyphenator.__init__")

	# From XServiceInfo
	def getImplementationName(self):
		return Hyphenator.IMPLEMENTATION_NAME

	def supportsService(self, serviceName):
		return serviceName in self.getSupportedServiceNames()

	def getSupportedServiceNames(self):
		return Hyphenator.SUPPORTED_SERVICE_NAMES

	# From XSupportedLocales
	def getLocales(self):
		return DivvunHandlePool.getInstance().getSupportedHyphenationLocales()

	def hasLocale(self, aLocale):
		return DivvunHandlePool.getInstance().supportsHyphenationLocale(aLocale)

	# From XHyphenator
	def hyphenate(self, word, locale, nMaxLeading, properties):
		logging.debug("Hyphenator.hyphenate")
		if len(word) > 10000:
			return None
		DivvunHandlePool.mutex.acquire()
		try:
			divvun = DivvunHandlePool.getInstance().getHandle(locale)
			if divvun is None:
				return None
			PropertyManager.getInstance().setValues(properties)

			minLeading = PropertyManager.getInstance().getHyphMinLeading()
			minTrailing = PropertyManager.getInstance().getHyphMinTrailing()
			wlen = len(word)

			# If the word is too short to be hyphenated, return no hyphenation points
			if wlen < PropertyManager.getInstance().getHyphMinWordLength() or wlen < minLeading + minTrailing:
				PropertyManager.getInstance().resetValues(properties)
				return None

			hyphenationPoints = divvun.getHyphenationPattern(word)
			if hyphenationPoints is None:
				PropertyManager.getInstance().resetValues(properties)
				return None

			# find the hyphenation point
			hyphenPos = -1
			i = wlen - minTrailing # The last generally allowed hyphenation point
			if i > nMaxLeading:
				i = nMaxLeading # The last allowed point on this line
			while i >= minLeading and hyphenPos == -1:
				if word[i] == '\'':
					i = i - 1
					continue
				if hyphenationPoints[i] == '-' or hyphenationPoints[i] == '=':
					hyphenPos = i
					break
				i = i - 1

			# return the result
			PropertyManager.getInstance().resetValues(properties)
			if hyphenPos != -1:
				return HyphenatedWord(word, hyphenPos - 1, locale)
			else:
				return None
		finally:
			DivvunHandlePool.mutex.release()

	def queryAlternativeSpelling(self, word, locale, index, properties):
		logging.debug("Hyphenator.queryAlternativeSpelling")
		# Implementing this might be necessary, although everything seems to work fine without it.
		return None

	def createPossibleHyphens(self, word, locale, properties):
		logging.debug("Hyphenator.createPossibleHyphens")
		wlen = len(word)
		if wlen > 10000:
			return None
		DivvunHandlePool.mutex.acquire()
		try:
			divvun = DivvunHandlePool.getInstance().getHandle(locale)
			if divvun is None:
				return None
			PropertyManager.getInstance().setValues(properties)

			# If the word is too short to be hyphenated, return no hyphenation points
			minLeading = PropertyManager.getInstance().getHyphMinLeading()
			minTrailing = PropertyManager.getInstance().getHyphMinTrailing()
			if wlen < PropertyManager.getInstance().getHyphMinWordLength() or wlen < minLeading + minTrailing:
				PropertyManager.getInstance().resetValues(properties)
				return None

			hyphenationPoints = divvun.getHyphenationPattern(word)
			if hyphenationPoints is None:
				PropertyManager.getInstance().resetValues(properties)
				return None

			hyphenSeq = []
			hyphenatedWord = ""
			for i in range(0, wlen):
				hyphenatedWord = hyphenatedWord + word[i]
				if i >= minLeading - 1 and i < wlen - minTrailing and hyphenationPoints[i + 1] == '-':
					hyphenSeq.append(i)
					hyphenatedWord = hyphenatedWord + "="

			res = PossibleHyphens(word, hyphenatedWord, hyphenSeq, locale)
			PropertyManager.getInstance().resetValues(properties)
			return res
		finally:
			DivvunHandlePool.mutex.release()

	# From XLinguServiceEventBroadcaster
	def addLinguServiceEventListener(self, xLstnr):
		logging.debug("Hyphenator.addLinguServiceEventListener")
		DivvunHandlePool.mutex.acquire()
		try:
			return PropertyManager.getInstance().addLinguServiceEventListener(xLstnr)
		finally:
			DivvunHandlePool.mutex.release()

	def removeLinguServiceEventListener(self, xLstnr):
		logging.debug("Hyphenator.removeLinguServiceEventListener")
		DivvunHandlePool.mutex.acquire()
		try:
			return PropertyManager.getInstance().removeLinguServiceEventListener(xLstnr)
		finally:
			DivvunHandlePool.mutex.release()

	# From XInitialization
	def initialize(self, seq):
		pass

	# From XServiceDisplayName
	def getServiceDisplayName(self, locale):
		if locale.Language == "fi":
			return "Tavutus (Divvun)"
		else:
			return "Hyphenator (Divvun)"

Hyphenator.IMPLEMENTATION_NAME = "divvun.Hyphenator"
Hyphenator.SUPPORTED_SERVICE_NAMES = ("com.sun.star.linguistic2.Hyphenator",)
