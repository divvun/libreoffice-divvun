# High-level interface between libdivvun and LO, should be testable
# without depending on any of the LO/UNO python modules.

import libdivvun
import logging


def partition(lst, pred):	# type: (List[T], Callable[[T], bool]) -> Tuple[List[T], List[T]]
	good, bad = [], []
	for x in lst:
		if pred(x):
			good.append(x)
		else:
			bad.append(x)
	return good, bad


def getToggleIds(uilanguage, handles):  # type: (str, Dict[str, Any]) -> Dict[str, str]
	"""Return the toggleIds of checker handles.
	"""
	toggleIds = {}		# type: Dict[str, str]
	def log(msg):
		logging.info("KBU: getToggleIds {}".format(msg))
	log("uilocale={}".format(uilanguage))
	for checklang, checker in handles.items():
		prefs = libdivvun.prefs_bytes(checker).asdict()
		log("prefs of checker for lang {} has pref l18n langs {}".format(checklang, prefs.keys()))
		# First add explanations from the other languages,
		# then those of the checker, then the UI language, so
		# the UI and checker language explanations are
		# preferred:
		p_uilang, p_notui = partition(prefs.items(), lambda lp: lp[0] == uilanguage)
		p_checklang, p_notcheckui = partition(p_notui, lambda lp: lp[0] == checklang)
		log("prefs of checker for lang {} has p_uilang {}".format(checklang, p_uilang))
		log("prefs of checker for lang {} has p_checklang {}".format(checklang, p_checklang))
		log("prefs of checker for lang {} has p_notcheckui {}".format(checklang, p_notcheckui))
		for _l, p in p_notcheckui:
			toggleIds.update(p.toggleIds.asdict())
		for _l, p in p_checklang:
			toggleIds.update(p.toggleIds.asdict())
		for _l, p in p_uilang:
			toggleIds.update(p.toggleIds.asdict())
	log("prefs of checker for lang {} has toggleIds {}".format(checklang, toggleIds))
	# Remove empty ones, just confusing:
	return { err:msg
		 for err,(msg, dsc) in toggleIds.items()
		 if err.strip() != "" and msg.strip() != "" }



# Test:
# $ LD_LIBRARY_PATH="../../src/.libs" PYTHONPATH="../../python/build/lib.linux-x86_64-3.6:oxt/pythonpath" python3 -c  '
#     import libdivvun;s=libdivvun.ArCheckerSpec("/usr/share/voikko/4/se.zcheck");smegram=s.getChecker("smegram",False);
#     import Divvun;print(Divvun.getToggleIds("se",{"se":smegram}))'
