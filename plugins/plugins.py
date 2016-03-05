#!/usr/bin/python
# encoding: utf-8
#
# virtinsttest - Virtual installation testing script
# Plugin API
#
# Copyright (c) 2015 Pieter Hollants <pieter@hollants.com>
# Licensed under the GNU Public License (GPL) version 3.
#

import logging

class VirtInstTestPlugin():
	""" Base class to be derived from by virtinsttest plugins. """

	@staticmethod
	def __init__(self, path, tempdir):
		""" Constructor method that tries to detect a supported OS at
		"path".

		In this method plugins should implement their OS detection
		logic. If a plugin recognizes the OS installation medium made
		available via "path", it should then do any other initialization
		steps necessary.

		If there is no supported OS detectable at "path", the method
		should raise an "UnsupportedOS" exception.

		:param string path: Path to a mounted OS installation medium
		:param string tempdir: Path to virtinsttest's tempdir

		:raises UnsupportedOS Raised if this plugin did not detect a
		supported OS. """

		# Initialize the logger for this object
		self.logger = logging.getLogger(self.__class__.__name__)

	class UnsupportedOS(Exception):
		pass

	def prepareInstallation(self):
		""" Does any prepatory work required to launch an installation. """

		pass

	def getOSVariant(self):
		""" Returns a "--os-variant" identifier for the virt-install
		command.

		:rtype: string """

		return self.osvariant

	def getVirtInstallFilesystemArgs(self):
		""" Returns a dictionary of "--filesystem" arguments for the
		virt-install command.

		The host's source directory is the key, the guest's target
		point the value.

		:rtype: dict """

		return {}

	def getVirtInstallInitrdInjectArgs(self):
		""" Returns a list of "--initrd-inject" arguments for the
		virt-install command.

		:rtype: list """

		return []

	def getVirtInstallExtraArgs(self):
		""" Returns a list of "--extra-args" arguments for the
		virt-install command.

		:rtype: list """

		return []

	def getFooterData(self, data):
		""" Returns a list of strings to be shown in the footer
		    placed on screenshots as the data currently processed by
		    the finite state machine.

		This function gets called by virtinsttest when a screenshot of
		the VM console has been taken and the footer text is being added
		to it. It can be used to augment the screenshot with one or
		multiple lines showing the current data (eg. logfile lines) that
		is being examined to decide on a possible installation state
		transition, thereby making it a bit easier to work out the right
		installation monitoring rules for a particular OS.

		"data" is a dictionary with the data returned by all of the
		plugin's data generation functions for the current installation
		state. It is indexed by the generation function name.

		:rtype: list """

		return []

	def getMaxFooterDataLines(self):
		""" Returns the maximum number of lines this plugin will add
		    to the footer placed on screenshots.

		When creating the video containing the VM console's screenshots
		virtinsttest must specify the frame height beforehand. Therefore
		a plugin that implements the getFooterDataForScreenshot() method
		must also specify the maximum number of text lines (= list
		elements) that method will return.

		:rtype: integer """

		return 0

	def getStats(self, data):
		""" Get statistics about data processing in virtinsttest.

		Plugins may use timing information and the information in "data"
		to generate statistics about virtinsttest's data processing, eg. the
		number of logfile lines processed per second.

		"data" is a dictionary with the data returned by all of the
		plugin's data generation functions for the current installation
		state. It is indexed by the generation function name.

		:rtype: string A log message with statistics """

		return
