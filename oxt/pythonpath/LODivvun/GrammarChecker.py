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
import unohelper # type:ignore
from com.sun.star.linguistic2 import XProofreader, ProofreadingResult, SingleProofreadingError # type:ignore
from com.sun.star.lang import XServiceInfo, XInitialization, XServiceDisplayName # type:ignore
from com.sun.star.beans import PropertyValue # type:ignore
from com.sun.star.text.TextMarkupType import PROOFREADING # type:ignore

from LODivvun.DivvunHandlePool import DivvunHandlePool
from LODivvun.PropertyManager import PropertyManager
from LODivvun.SettingsEventHandler import readIgnoredRules, saveIgnoredRules
import libdivvun

class GrammarChecker(unohelper.Base, XServiceInfo, XProofreader, XInitialization, XServiceDisplayName):

	def __init__(self, ctx, *args):
		logging.debug("GrammarChecker.__init__")

	# From XServiceInfo
	def getImplementationName(self):
		return GrammarChecker.IMPLEMENTATION_NAME

	def supportsService(self, serviceName):
		return serviceName in self.getSupportedServiceNames()

	def getSupportedServiceNames(self):
		return GrammarChecker.SUPPORTED_SERVICE_NAMES

	# From XSupportedLocales
	def getLocales(self):
		return DivvunHandlePool.getInstance().getSupportedGrammarLocales()

	def hasLocale(self, aLocale):
		logging.info("haslocale %s for %s", DivvunHandlePool.getInstance().supportsGrammarLocale(aLocale), aLocale)
		return DivvunHandlePool.getInstance().supportsGrammarLocale(aLocale)

	# From XProofreader
	def isSpellChecker(self):
		return False

	def doProofreading(self, aDocumentIdentifier, aText, aLocale, nStartOfSentencePos, nSuggestedBehindEndOfSentencePosition, aProperties):
		logging.debug("GrammarChecker.doProofreading")
		result = ProofreadingResult()
		result.aDocumentIdentifier = aDocumentIdentifier
		result.xFlatParagraph = None
		result.aText = aText
		result.aLocale = aLocale
		result.nStartOfSentencePosition = nStartOfSentencePos
		result.nBehindEndOfSentencePosition = nSuggestedBehindEndOfSentencePosition
		result.xProofreader = self
		# We read from registry on each check – it probably
		# doesn't change most of the time, but it *can* change
		# if user edited the plugin options, so this is at
		# least safe:
		ignoredRules = readIgnoredRules() # TODO: get from PropertyManager instead, see reloadDivvunSettings

		DivvunHandlePool.mutex.acquire()
		try:
			instance = DivvunHandlePool.getInstance()
			if instance is None:
				logging.error("GrammarChecker.doProofreading could not initialize libdivvun!")
				return result
			divvun = instance.getHandle(aLocale)
			if divvun is None:
				logging.error("GrammarChecker.doProofreading couldn't get an instance for locale %s"%(aLocale,))
				logging.error("DivvunHandlePool.initializationErrors = %s"%(instance.getInitializationStatus(),))
				return result

			gcErrors = []
			logging.info("Checking '%s', nStartOfSentencePos=%d, nSuggestedBehindEndOfSentencePosition=%d",
					aText, nStartOfSentencePos, nSuggestedBehindEndOfSentencePosition)
			for dError in libdivvun.proc_errs_bytes(divvun, aText):
				startPos = dError.beg
				errorLength = dError.end - dError.beg
				logging.info("dError on form=%s at (%d,%d) replacements: %s",
						dError.form, dError.beg, dError.end, dError.rep)
				if dError.beg < result.nStartOfSentencePosition:
					logging.info("beg %d < result.nStartOfSentencePosition %d, continue",
							dError.beg, result.nStartOfSentencePosition)
					continue
				if dError.beg >= result.nBehindEndOfSentencePosition:
					logging.info("beg %d >= result.nBehindEndOfSentencePosition %d, break",
							dError.beg, result.nBehindEndOfSentencePosition)
					break
				if dError.beg + errorLength > result.nBehindEndOfSentencePosition:
					logging.info("dError.beg %d + errorLength %d > result.nBehindEndOfSentencePosition %d, incf",
							dError.beg, errorLength, result.nBehindEndOfSentencePosition)
					result.nBehindEndOfSentencePosition = dError.beg + errorLength
				logging.info("dError on form=%s at (%d,%d) replacements: %s",
						dError.form,
						dError.beg, dError.end,
						dError.rep)
				ruleIdentifier = dError.err
				if ruleIdentifier in ignoredRules:
					logging.debug("Ignored error with rule " + ruleIdentifier)
					continue

				suggestions = dError.rep
				gcError = SingleProofreadingError()
				gcErrors.append(gcError)
				gcError.nErrorStart = startPos
				gcError.nErrorLength = errorLength
				gcError.nErrorType = PROOFREADING
				comment = dError.dsc
				gcError.aShortComment = comment
				gcError.aFullComment = comment
				gcError.aRuleIdentifier = ruleIdentifier

				if False:  # We are not web yet, TODO
				    detailUrl = PropertyValue()
				    detailUrl.Name = "FullCommentURL"
				    detailUrl.Value = "http://divvun.no/gchelp/" + aLocale.Language + "/" + ruleIdentifier + ".html"
				    gcError.aProperties = (detailUrl,)

				# add suggestions
				if len(suggestions) > 0:
					gcError.aSuggestions = tuple(suggestions)

			result.aErrors = tuple(gcErrors)
			result.nStartOfNextSentencePosition = result.nBehindEndOfSentencePosition
			logging.info("return result, errors: %d", len(result.aErrors))
			return result
		finally:
			DivvunHandlePool.mutex.release()

	def ignoreRule(self, ruleIdentifier, locale):
		logging.debug("Ignoring rule " + ruleIdentifier)
		ignoredRules = { ruleIdentifier }.union(readIgnoredRules())
		saveIgnoredRules(ignoredRules)

	def resetIgnoreRules(self):
		logging.debug("Reset ignored rules")
		saveIgnoredRules(set())

	# From XInitialization
	def initialize(self):
		pass

	# From XServiceDisplayName
	def getServiceDisplayName(self, locale):
		if locale.Language == "fi":
			return "Kieliopin tarkistus (Divvun)"
		else:
			return "Grammar checker (Divvun)"

GrammarChecker.IMPLEMENTATION_NAME = "divvun.GrammarChecker"
GrammarChecker.SUPPORTED_SERVICE_NAMES = ("com.sun.star.linguistic2.Proofreader",)
