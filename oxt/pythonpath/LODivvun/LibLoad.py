# Libreoffice-divvun: Linguistic extension for LibreOffice
# Copyright (C) 2018 Kevin Brubeck Unhammer <unhammer@fsfe.org>
#
# This Source Code Form is subject to the terms of the Mozilla Public License,
# v. 2.0. If a copy of the MPL was not distributed with this file, You can
# obtain one at http://mozilla.org/MPL/2.0/.
#
# Alternatively, the contents of this file may be used under the terms of
# the GNU General Public License Version 3 or later (the "GPL"), in which
# case the provisions of the GPL are applicable instead of those above.

import os
import re
import uno
import sys
import platform
from ctypes import CDLL
import traceback
import logging
import unohelper
from com.sun.star.awt.MessageBoxType import ERRORBOX
from com.sun.star.awt.MessageBoxButtons import BUTTONS_OK

def messageBox(messageText):
	ctx = uno.getComponentContext()
	sManager = ctx.ServiceManager
	toolkit = sManager.createInstance("com.sun.star.awt.Toolkit")
	msgbox = toolkit.createMessageBox(None, ERRORBOX, BUTTONS_OK, "Error initializing Divvun", messageText)
	return msgbox.execute()


def platformSuffix():
	if os.name == "nt":
		logging.warn("Windows completely untested")
		return "dll"
	if sys.platform == "darwin":
		return "dylib"
	else:
		return "so"

def loadLibs():
	# This function has to be in a module (not lodivvun.py) to work
	dname = os.path.dirname(sys.modules[__name__].__file__)
	expectedSuffix = "pythonpath/LODivvun"
	if dname.endswith(expectedSuffix):
		dname = dname[:-len(expectedSuffix )]
	else:
		logging.warning("{} found in unexpected directory {}".format(__name__, dname))
	searchPath = os.path.join(dname,
				  "divvun",
				  platform.system() + "-" + "-".join(platform.architecture()))
	if not os.path.exists(searchPath):
		# TODO: Is this the best way to handle this?
		# We *do* want to show error messages if bundled libs couldn't be loaded when we are in a bundle, and vice versa system.
		logging.debug("C library search path {} does not exists, assuming we should use system libraries".format(searchPath))
		return
	else:
		logging.debug("Loading C libraries from search path {}".format(searchPath))
	# Keep libdivvun.so last, since it depends on the others:
	cnames = ["cg3", "archive", "hfst", "hfstospell", "divvun"]
	suffix = platformSuffix()
	clibs = {}
	loadingFailed = False
	for libname in cnames:
		matches = [f for f in os.listdir(searchPath)
			   if re.match('^lib{}([.][0-9]+)?[.]{}'.format(libname, suffix), f)]
		if matches == []:
			msg = "Couldn't find lib{}.{} in search path {}!".format(libname, suffix, searchPath)
			logging.warning(msg)
			if not loadingFailed:
				messageBox(msg)
			loadingFailed = True
			continue
		try:
			# Use the shortest match (ie. one with no version string if one exists)
			libbase = sorted(matches, key=len)
			clibs[libname] = CDLL(os.path.join(searchPath, libbase))
		except OSError as e:
			msg = "OSError on loading C library {}: {}".format(libname, e)
			logging.warning(msg)
			if not loadingFailed:
				messageBox(msg)
			loadingFailed = True
