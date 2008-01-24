/* Openoffice.org-voikko: Finnish linguistic extension for OpenOffice.org
 * Copyright (C) 2007 Harri Pitkänen <hatapitk@iki.fi>
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 2
 * of the License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
 *********************************************************************************/

#include <hspell.h>

#include "SpellChecker.hxx"
#include "SpellAlternatives.hxx"
#include "../common.hxx"

namespace hspell {

SpellChecker::SpellChecker(uno::Reference<uno::XComponentContext> const & context) :
	cppu::WeakComponentImplHelper5
	     <lang::XServiceInfo,
	      linguistic2::XSpellChecker,
	      linguistic2::XLinguServiceEventBroadcaster,
	      lang::XInitialization,
	      lang::XServiceDisplayName>(m_aMutex),
	compContext(context) { }

OUString SAL_CALL SpellChecker::getImplementationName() throw (uno::RuntimeException) {
	return getImplementationName_static();
}

sal_Bool SAL_CALL SpellChecker::supportsService(const OUString & serviceName)
	throw (uno::RuntimeException) {
	uno::Sequence<OUString> serviceNames = getSupportedServiceNames();
	for (sal_Int32 i = 0; i < serviceNames.getLength(); i++)
		if (serviceNames[i] == serviceName) return sal_True;
	return sal_False;
}

uno::Sequence<OUString> SAL_CALL SpellChecker::getSupportedServiceNames() throw (uno::RuntimeException) {
	return getSupportedServiceNames_static();
}

uno::Sequence<lang::Locale> SAL_CALL SpellChecker::getLocales() throw (uno::RuntimeException) {
	uno::Sequence<lang::Locale> locales(1);
	locales.getArray()[0] = lang::Locale(A2OU("he"), A2OU("IL"), OUString());
	return locales;
}

sal_Bool SAL_CALL SpellChecker::hasLocale(const lang::Locale & aLocale) throw (uno::RuntimeException) {
	if (aLocale.Language == A2OU("he")) return sal_True;
	else return sal_False;
}

sal_Bool SAL_CALL SpellChecker::isValid(const OUString & aWord, const lang::Locale &,
	                              const uno::Sequence<beans::PropertyValue> & aProperties)
	throw (uno::RuntimeException, lang::IllegalArgumentException) {
	osl::MutexGuard vmg(getVoikkoMutex());
	if (!voikko_initialized) return sal_False;
	OString oWord = OUStringToOString(aWord, RTL_TEXTENCODING_ISO_8859_8);
	const char * c_str = oWord.getStr();

	thePropertyManager->setValues(aProperties);
	// VOIKKO_DEBUG_2("SpellChecker::isValid: c_str: '%s'\n", c_str);
	int preflen;
	int result = hspell_check_word(dict, c_str, &preflen);
	// VOIKKO_DEBUG_2("SpellChecker::isValid: result = %i\n", result);
	thePropertyManager->resetValues(aProperties);
	if (result) return sal_True;
	else return sal_False;
}

uno::Reference<linguistic2::XSpellAlternatives> SAL_CALL SpellChecker::spell(
	const OUString & aWord, const lang::Locale &,
	const uno::Sequence<beans::PropertyValue> & aProperties)
	throw (uno::RuntimeException, lang::IllegalArgumentException) {
	
	// Check if diagnostic message should be returned
	if (aWord.equals(A2OU("VoikkoGetStatusInformation"))) {
		SpellAlternatives * alternatives = new SpellAlternatives();
		alternatives->word = aWord;
		uno::Sequence<OUString> suggSeq(1);
		if (thePropertyManager != 0)
			suggSeq.getArray()[0] = thePropertyManager->getInitializationStatus();
		else
			suggSeq.getArray()[0] = A2OU("PropertyManager does not exist");
		alternatives->alternatives = suggSeq;
		return alternatives;
	}
	
	osl::MutexGuard vmg(getVoikkoMutex());
	if (!voikko_initialized) return 0;
	OString oWord = OUStringToOString(aWord, RTL_TEXTENCODING_ISO_8859_8);
	const char * c_str = oWord.getStr();

	thePropertyManager->setValues(aProperties);
	int preflen;
	if (hspell_check_word(dict, c_str, &preflen)) {
		thePropertyManager->resetValues(aProperties);
		return 0;
	}

	struct corlist cl;
	corlist_init(&cl);
	hspell_trycorrect(dict, c_str, &cl);
	thePropertyManager->resetValues(aProperties);
	SpellAlternatives * alternatives = new SpellAlternatives();
	alternatives->word = aWord;
	int scount = corlist_n(&cl);
	if (scount == 0) return alternatives;
	uno::Sequence<OUString> suggSeq(scount);
	OUString * suggStrings = suggSeq.getArray();
	OString ostr;
	for (int i = 0; i < scount; i++) {
		ostr = OString(corlist_str(&cl, i));
		suggStrings[i] = OStringToOUString(ostr, RTL_TEXTENCODING_ISO_8859_8);
	}
	corlist_free(&cl);

	alternatives->alternatives = suggSeq;
	return alternatives;
}

sal_Bool SAL_CALL SpellChecker::addLinguServiceEventListener(
	const uno::Reference<linguistic2::XLinguServiceEventListener> & xLstnr)
	throw (uno::RuntimeException) {
	osl::MutexGuard vmg(getVoikkoMutex());
	VOIKKO_DEBUG("SpellChecker::addLinguServiceEventListener");
	if (thePropertyManager != 0)
		return thePropertyManager->addLinguServiceEventListener(xLstnr);
	else return sal_False;
}

sal_Bool SAL_CALL SpellChecker::removeLinguServiceEventListener(
	const uno::Reference<linguistic2::XLinguServiceEventListener> & xLstnr)
	throw (uno::RuntimeException) {
	osl::MutexGuard vmg(getVoikkoMutex());
	VOIKKO_DEBUG("SpellChecker::removeLinguServiceEventListener");
	if (thePropertyManager != 0)
		return thePropertyManager->removeLinguServiceEventListener(xLstnr);
	else return sal_False;
}

void SAL_CALL SpellChecker::initialize(const uno::Sequence<uno::Any> &)
	throw (uno::RuntimeException, uno::Exception) {
	osl::MutexGuard vmg(getVoikkoMutex());
	VOIKKO_DEBUG("SpellChecker::initialize");
	if (thePropertyManager == 0) thePropertyManager = new PropertyManager(compContext);
	thePropertyManager->initialize();
}

OUString SAL_CALL SpellChecker::getServiceDisplayName(const lang::Locale & aLocale)
	throw (uno::RuntimeException) {
	return A2OU("Hebrew spellchecker (Hspell)");
}

void SAL_CALL SpellChecker::disposing() {
	VOIKKO_DEBUG("SpellChecker::disposing");
}

}
