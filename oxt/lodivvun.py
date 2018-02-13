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

import os
import uno
import sys
import traceback
import logging
import unohelper
from com.sun.star.awt.MessageBoxType import ERRORBOX
from com.sun.star.awt.MessageBoxButtons import BUTTONS_OK

logging.basicConfig(format='%(asctime)s,%(msecs)d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s',
    datefmt='%d-%m-%Y:%H:%M:%S')

if "DIVVUN_DEBUG" in os.environ:
	logging.getLogger().setLevel(logging.DEBUG)

logging.debug("sys.path: {}".format(sys.path))

def messageBox(messageText):
	ctx = uno.getComponentContext()
	sManager = ctx.ServiceManager
	toolkit = sManager.createInstance("com.sun.star.awt.Toolkit")
	msgbox = toolkit.createMessageBox(None, ERRORBOX, BUTTONS_OK, "Error initializing Divvun", messageText)
	return msgbox.execute()

# We try importing libdivvun before any of the other modules that may
# depend on libdivvun (this includes PropertyManager!), so we can
# catch the exception and show it to the user:
loadingFailed = False
try:
    import libdivvun
    logging.debug("libdivvun.searchPaths(): {}".format(list(libdivvun.searchPaths())))
    from LODivvun.PropertyManager import PropertyManager
    from LODivvun.SettingsEventHandler import SettingsEventHandler
    from LODivvun.SpellChecker import SpellChecker
    from LODivvun.Hyphenator import Hyphenator
    from LODivvun.GrammarChecker import GrammarChecker
except OSError as e:
	loadingFailed = True
	messageBox("OSError: {0}".format(e))
except:
	loadingFailed = True
	msg = "\n".join(["Please report this to http://divvun.no/contact.html :\n",
			 "sys.version = " + str(sys.version),
			 "sys.path = " + str(sys.path),
			 "sys.prefix = " + str(sys.prefix),
			 "sys.exec_prefix = " + str(sys.exec_prefix),
			 "\nTraceback:",
			 "".join(traceback.format_exception(*sys.exc_info()))])
	logging.warn(msg)
	messageBox(msg)

# Presumably this can fail too, catch the same kinds of errors here:
if not PropertyManager.loadingFailed:
	try:
		# Force initialization of property manager so that it is done before anything else.
		PropertyManager.getInstance()
		# name of g_ImplementationHelper is significant, Python component loader expects to find it
		g_ImplementationHelper = unohelper.ImplementationHelper()
		g_ImplementationHelper.addImplementation(SettingsEventHandler, \
		                    SettingsEventHandler.IMPLEMENTATION_NAME,
		                    SettingsEventHandler.SUPPORTED_SERVICE_NAMES,)
		g_ImplementationHelper.addImplementation(SpellChecker, \
		                    SpellChecker.IMPLEMENTATION_NAME,
		                    SpellChecker.SUPPORTED_SERVICE_NAMES,)
		g_ImplementationHelper.addImplementation(Hyphenator, \
		                    Hyphenator.IMPLEMENTATION_NAME,
		                    Hyphenator.SUPPORTED_SERVICE_NAMES,)
		g_ImplementationHelper.addImplementation(GrammarChecker, \
		                    GrammarChecker.IMPLEMENTATION_NAME,
		                    GrammarChecker.SUPPORTED_SERVICE_NAMES,)
	except OSError as e:
		PropertyManager.loadingFailed = True
		messageBox("OSError: {0}".format(e))
	except:
		PropertyManager.loadingFailed = True
		msg = "\n".join(traceback.format_exception(*sys.exc_info()))
		logging.warn(msg)
		messageBox(msg)
