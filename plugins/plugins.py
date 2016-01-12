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
		supported OS.
		"""

		# Initialize the logger for this object
		self.logger = logging.getLogger(self.__class__.__name__)

	class UnsupportedOS(Exception):
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

		return None

	def getVirtInstallInitrdInjectArgs(self):
		""" Returns an array of "--initrd-inject" arguments for the
		virt-install command.

		:rtype: array """

		return None

	def getVirtInstallExtraArgs(self):
		""" Returns an array of "--extra-args" arguments for the
		virt-install command.

		:rtype: array """

		return None
