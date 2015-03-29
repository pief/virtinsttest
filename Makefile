#
# virtinsttest - Virtual installation testing script
#
# Copyright (c) 2015 Pieter Hollants <pieter@hollants.com>
# Licensed under the GNU Public License (GPL) version 3.
#
# Makefile for Git repository-based builds
#

# The version is derived from the newest git tag and commits after it
# RPM does not allow dashes in version strings
VERSION := $(shell git describe 2>/dev/null | sed 's,-,_next,;s,-,_,')

# Directory name in the source distribution archive
DISTNAME := virtinsttest-$(VERSION)

all: help

help:
	@echo
	@echo "            virtinsttest - Virtual installation testing script"
	@echo "         Copyright (c) 2015 Pieter Hollants <pieter@hollants.com>"
	@echo
	@[ -n "$(VERSION)" ] && V="$(VERSION)" || V="??? (no git tags defined yet)"; \
	echo "Version from \"git describe\": $$V"
	@echo
	@echo "Targets:"
	@echo " install    - Install locally"
	@echo " srcdist    - Create source distribution archive in .tar.bz2 format"
	@echo " rpms       - Build RPMs for the current distribution"
	@echo " clean      - Clean up"
	@echo

install:
	@make --no-print-directory -f Makefile.srcdist install PREFIX=$(PREFIX)/usr

.PHONY: ChangeLog
ChangeLog:
	@if [ -z "$(VERSION)" ] ; then \
		echo "ERROR: No git tags defined yet, can't deduce version!"; \
		exit 1; \
	fi
	@[ -e $@ ] && rm $@ || true
	@CURRENT=$(VERSION); \
	set -- `git tag -l | egrep ^[[:digit:]]+.[[:digit:]]+\(.[[:digit:]]+\)?$ | sort -r`; \
	if [ "$$CURRENT" == "$$1" ] ; then shift; fi; \
	until [ -z "$$CURRENT" ] ; do \
		if [ -n "$$1" ] ; then \
			LINE="Changes from v$$1 to v$$CURRENT"; \
			PREV="$$1.."; \
		else \
			LINE="Initial version $$CURRENT"; \
			PREV=""; \
		fi; \
		echo >>$@; \
		echo $$LINE >>$@; \
		printf "%*s\n" $${#LINE} | tr ' ' '=' >>$@; \
		echo >>$@; \
		git log \
			--no-merges \
			--format="* %ad - %aN <%ae>%n%n%+w(75,2,2)%s%n%+b%n(Git commit %H)%n" \
			$$PREV$$CURRENT >>$@; \
		CURRENT=$$1; \
		shift || true; \
	done

dist:
	@mkdir dist

srcdist: dist/$(DISTNAME).tar.bz2

.PHONY: dist/$(DISTNAME).tar.bz2
dist/$(DISTNAME).tar.bz2: ChangeLog dist
	@[ -e dist/$(DISTNAME) ] && rm -rf dist/$(DISTNAME) || true
	@mkdir -p dist/$(DISTNAME) || exit 1
	@for FILE in `find . -regex "./\(.git.*\|dist\|plugins\/*.pyc\|virtinsttest.spec.in\)" -prune -o -type f -printf "%P "`; do \
		cp -a --parents $${FILE} dist/$(DISTNAME)/ || exit 1; \
	done
	@sed -i "s,^VirtInstTestVersion *=.*,VirtInstTestVersion = $(VERSION)," dist/$(DISTNAME)/virtinsttest
	@mv dist/$(DISTNAME)/Makefile.srcdist dist/$(DISTNAME)/Makefile
	@sed "s/@VIRTINSTTEST_VERSION@/$(VERSION)/" \
	  virtinsttest.spec.in \
	  >dist/$(DISTNAME)/virtinsttest.spec
	@PKGREMAIL=`git config user.email`; \
	if [ -z "$$PKGREMAIL" ] ; then \
		PKGREMAIL="`whoami`@`hostname`"; \
	fi; \
	CURRENT=`git describe`; \
	set -- `git tag -l | egrep ^[[:digit:]]+.[[:digit:]]+\(.[[:digit:]]+\)?$ | sort -r`; \
	if [ "$$CURRENT" == "$$1" ] ; then shift; fi; \
	until [ -z "$$CURRENT" ] ; do \
		if [ -n "$$1" ] ; then \
			LINE="Update to version $$CURRENT"; \
		else \
			LINE="Initial version $$CURRENT"; \
		fi; \
		GITDATE=`git log --format="%ad" --date=iso -n1 $$CURRENT`; \
		OURDATE=`LANG=C date -d "$$GITDATE" +"%a %b %d %Y"`; \
		echo >>dist/$(DISTNAME)/virtinsttest.spec "* $$OURDATE $$PKGREMAIL"; \
		echo >>dist/$(DISTNAME)/virtinsttest.spec "- $$LINE"; \
		echo >>dist/$(DISTNAME)/virtinsttest.spec; \
		CURRENT=$$1; \
		shift || true; \
	done
	@cd dist && tar cjf $(DISTNAME).tar.bz2 $(DISTNAME) || exit 1
	@rm -rf dist/$(DISTNAME)
	@echo Created source distribution archive as $@

rpms: dist/$(DISTNAME).tar.bz2
	@mkdir -p dist/RPMBUILD/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS} || exit 1
	@cd dist/RPMBUILD/SPECS && tar xjvf ../../$(DISTNAME).tar.bz2 $(DISTNAME)/virtinsttest.spec --strip-components=1 || exit 1
	@cp -a dist/$(DISTNAME).tar.bz2 dist/RPMBUILD/SOURCES/ || exit 1
	@cd dist/RPMBUILD && \
	rpmbuild \
		--define "%_topdir $$(pwd)" \
		-ba SPECS/virtinsttest.spec || exit 1
	@find dist/RPMBUILD -name *.rpm -exec cp -a {} dist/ \; || exit 1
	@rm -r dist/RPMBUILD || true
	@echo RPMs can be found in the dist/ directory

clean:
	@[ -e "*.pyc" ] && rm *.pyc || true
	@[ -e "plugins/*.pyc" ] && rm plugins/*.pyc || true
	@[ -e ChangeLog ] && rm ChangeLog || true
	@[ -e dist ] && rm -rf dist || true
