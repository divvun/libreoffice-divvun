# Libreoffice-divvun: Linguistic extension for LibreOffice
# Copyright (C) 2005 - 2015 Harri Pitkänen <hatapitk@iki.fi>
#
# This Source Code Form is subject to the terms of the Mozilla Public License,
# v. 2.0. If a copy of the MPL was not distributed with this file, You can
# obtain one at http://mozilla.org/MPL/2.0/.
# 
# Alternatively, the contents of this file may be used under the terms of
# the GNU General Public License Version 3 or later (the "GPL"), in which
# case the provisions of the GPL are applicable instead of those above.
###############################################################################

# ===== Build settings =====

# Version number of the libreoffice-divvun extension
DIVVUN_VERSION=5.0

# If you want to have a license text to be displayed upon the installation
# of this extension, uncomment the following.
# SHOW_LICENSE=1

# Setting this option to 1 causes ugly warnings to be added to visible places
# in the extension without removing any functionality (codename "tekstintuho").
# Useful for binary builds that are released for public testing.
# SHOW_UGLY_WARNINGS=1

# Destination directory when installing unpacked extension with
# make install-unpacked
DESTDIR=/usr/lib/libreoffice-divvun

# Uncomment the following (or use "make oxt STANDALONE_EXTENSION=1") if you want
# to build a standalone extension.
# Files to be delivered with the extension must be placed under directory divvun/
# and libdivvun.py and _libdivvun*{dll,so} under oxt/pythonpath/
# STANDALONE_EXTENSION=1

# === End build settings ===

# Platform specific variables
ifdef SystemRoot # Windows
	COPYDIR=xcopy /E /I
	COPY=copy
	PS="\\"
	MKDIR=mkdir
else
	COPYDIR=cp -r
	COPY=cp
	PS="/"
	MKDIR=mkdir -p
endif
ZIP=zip
SED=sed
FIND=find

# Build extension package name
ifdef SHOW_UGLY_WARNINGS
        DIVVUN_PACKAGENAME:=tekstintuho
else
        DIVVUN_PACKAGENAME:=divvun
endif

SRC_AND_DIST=config.xcu config.xcs icon.png SettingsDialog.xdl SettingsDialog_en_US.properties \
             SettingsDialog_fi_FI.properties SettingsDialog_en_US.default SettingsDialog.xcu Linguistic.xcu \
             divvun.components META-INF/manifest.xml lodivvun.py \
             pythonpath/LODivvun/__init__.py \
             pythonpath/LODivvun/LibLoad.py \
             pythonpath/LODivvun/SettingsEventHandler.py pythonpath/LODivvun/SpellChecker.py pythonpath/LODivvun/DivvunHandlePool.py \
             pythonpath/LODivvun/SpellAlternatives.py pythonpath/LODivvun/PropertyManager.py pythonpath/LODivvun/Hyphenator.py \
             pythonpath/LODivvun/HyphenatedWord.py pythonpath/LODivvun/PossibleHyphens.py pythonpath/LODivvun/GrammarChecker.py
SRCDIST=COPYING Makefile README ChangeLog oxt/description.xml.template \
        $(patsubst %,oxt/%,$(SRC_AND_DIST)) \
        oxt/icon.svg oxt/license_fi.txt oxt/license_en-US.txt

COPY_TEMPLATES=$(SRC_AND_DIST)

ifdef SHOW_LICENSE
	COPY_TEMPLATES+=license_fi.txt license_en-US.txt
endif

ifdef STANDALONE_EXTENSION
	STANDALONE_EXTENSION_FILES=$(shell find oxt/divvun \( -type f -o -type l \) '!' -name '.*' '!' -path 'oxt/divvun*/.*')
	COPY_TEMPLATES+=pythonpath/libdivvun.py
	COPY_TEMPLATES+=$(shell cd oxt && find pythonpath \( -type f -o -type l \) -name '_libdivvun*' -print)
else
	STANDALONE_EXTENSION_FILES=
endif

EXTENSION_FILES=build/oxt/description.xml \
	      $(patsubst %,build/%,$(STANDALONE_EXTENSION_FILES)) \
	      $(patsubst %,build/oxt/%,$(COPY_TEMPLATES))

# Targets
.PHONY: extension-files oxt install-unpacked all clean dist-gzip

extension-files : $(EXTENSION_FILES)

oxt: $(EXTENSION_FILES)
	cd build/oxt && $(ZIP) -r -9 ../$(DIVVUN_PACKAGENAME).oxt \
	   $(patsubst build/oxt/%,%,$^)

all: oxt

install-unpacked: extension-files
	install -m 755 -d "$(DESTDIR)" "$(DESTDIR)/META-INF"
	install -m 644 build/oxt/META-INF/manifest.xml "$(DESTDIR)/META-INF"
	install -m 644 build/oxt/description.xml \
	               $(patsubst %,build/%,$(STANDALONE_EXTENSION_FILES)) \
	               $(patsubst %,build/oxt/%,$(COPY_TEMPLATES)) $(DESTDIR)

# Sed scripts for modifying templates
DESCRIPTION_SEDSCRIPT:=s/DIVVUN_VERSION/$(DIVVUN_VERSION)/g
ifdef SHOW_LICENSE
	DESCRIPTION_SEDSCRIPT:=$(DESCRIPTION_SEDSCRIPT);/SHOW_LICENSE/d
endif
ifdef SHOW_UGLY_WARNINGS
	DESCRIPTION_SEDSCRIPT:=$(DESCRIPTION_SEDSCRIPT);s/Divvun/TEKSTINTUHO/g
endif
DESCRIPTION_SEDSCRIPT:="$(DESCRIPTION_SEDSCRIPT)"

# Create extension files
build/oxt/description.xml: oxt/description.xml.template
	-$(MKDIR) $(subst /,$(PS),$(@D))
	$(SED) -e $(DESCRIPTION_SEDSCRIPT) < $^ > $@

$(patsubst %,build/oxt/%,$(COPY_TEMPLATES)): build/oxt/%: oxt/%
	-$(MKDIR) $(subst /,$(PS),$(@D))
	$(COPY) "$(subst /,$(PS),$^)" "$(subst /,$(PS),$@)"

$(patsubst %,build/%,$(STANDALONE_EXTENSION_FILES)): build/%: %
	-$(MKDIR) $(subst /,$(PS),$(@D))
	$(COPYDIR) "$(subst /,$(PS),$^)" "$(subst /,$(PS),$@)"


# Rules for creating the source distribution
dist-gzip: libreoffice-divvun-$(DIVVUN_VERSION).tar.gz

libreoffice-divvun-$(DIVVUN_VERSION).tar.gz: $(patsubst %,libreoffice-divvun-$(DIVVUN_VERSION)/%, \
	                                      $(sort $(SRCDIST)))
	tar c --group 0 --owner 0 libreoffice-divvun-$(DIVVUN_VERSION) | gzip -9 > $@

$(patsubst %,libreoffice-divvun-$(DIVVUN_VERSION)/%, $(sort $(SRCDIST))): \
	libreoffice-divvun-$(DIVVUN_VERSION)/%: %
	install --mode=644 -D $^ $@


# The clean target
clean:
	rm -rf build libreoffice-divvun-$(DIVVUN_VERSION)
	rm -f libreoffice-divvun-$(DIVVUN_VERSION).tar.gz
	rm -rf oxt/divvun/
	rm -f oxt/pythonpath/_libdivvun.*.so
