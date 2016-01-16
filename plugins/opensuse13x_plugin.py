#!/usr/bin/python
# encoding: utf-8
#
# virtinsttest - Virtual installation testing script
# Plugin for openSUSE 13.2 (and newer)
#
# Copyright (c) 2015 Pieter Hollants <pieter@hollants.com>
# Licensed under the GNU Public License (GPL) version 3.
#

import os, re, time, subprocess, shutil

from plugins import *

class OpenSUSE13xPlugin(VirtInstTestPlugin):
	def __init__(self, path, tempdir):
		VirtInstTestPlugin.__init__(self, path, tempdir)

		# Try to detect openSUSE medium and version
		self.osversion = self._ProbeOpenSUSEVersion(path)
		if self.osversion:
			msg = "Detected openSUSE version: {0}".format(self.osversion)
			self.logger.info(msg)
		else:
			raise VirtInstTestPlugin.UnsupportedOS()

		# Make detected version available via variables used by
		# standard getter
		self.osvariant = "opensuse{0}".format(self.osversion)
		self.logger.debug("Deduced osvariant: {0}".format(self.osvariant))

		# For openSUSE distributions, installation monitoring will be
		# done by observing YaST's logfiles, for which we need a
		# "y2logs" directory that will be shared between host and guest
		self.logger.info("Creating \"y2logs\" directory (will be shared with VM via 9p)...")
		self.y2logs_dir = os.path.join(tempdir, "y2logs")
		os.mkdir(self.y2logs_dir)

		# openSUSE installation media lack the 9p kernel modules
		# required for sharing directories between host and guest, so
		# we retrofit them via the "Driver Update Disk" (DUD) mechanism
		self.dudfile = self._GenerateDUD(path, tempdir)

		# Initialize for getFooterData()
		self.logbuf = []

		# Initialize statistics vars
		self.lastlineno = 0
		self.laststatstime = 0
		self.lps_samples = 0
		self.min_lps = 0
		self.avg_lps = 0
		self.max_lps = 0

	def _ProbeOpenSUSEVersion(self, path):
		""" Probes for an OpenSUSE medium and its version.

		path: The path to a mounted supposed openSUSE medium

		:rtype: string|None The detected version number """

		# The most robust way to detect a openSUSE distribution seems
		# to be via the installation medium's bootloader menu
		try:
			gfxbootfile = os.path.join(path, "boot/x86_64/loader/gfxboot.cfg")
			with open(gfxbootfile) as f:
				for line in f:
					match = re.match(r"^product=openSUSE (.+)$", line)
					if match and match.group(1):
						return match.group(1)
						break
		except IOError as e:
			pass

		return None

	def _GenerateDUD(self, path, tempdir):
		""" Creates a Driver Update Disk (DUD) image to retrofit 9p
		    filesystem sharing.

		path: The path to the mounted openSUSE ISO to create a DUD for
		tempdir: The directory to create the .cpio.gz archive in

		:rtype: string The filename of the DUD .cpio.gz archive """

		self.logger.info("Creating Driver Update Disk (DUD) image to retrofit 9p filesystem sharing:")

		self.logger.info("- Creating DUD directory structure...")
		duddir = os.path.join(tempdir, "dud")
		dudinstalldir = os.path.join(
			duddir,
			"linux/suse/x86_64-{0}/install".format(self.osversion)
		)
		os.makedirs(dudinstalldir, 0755)

		self.logger.info("- Creating dud.config...")
		with open(os.path.join(duddir, "dud.config"), "w") as f:
			f.write("UpdateName: virtinsttest DUD for openSUSE {0}\n".format(self.osversion))
			f.write("UpdateID: e82ffff3-34d9-4f6b-bd58-b638f234776\n")

		self.logger.info("- Creating DUD update.pre script...")
		with open(
			os.path.join(
				duddir,
				"linux/suse/x86_64-{0}/install/update.pre".format(self.osversion)
			), "w"
		) as f:
			f.write("""#!/bin/bash

		echo "*** virtinsttest DUD update.pre running ***"

		echo "Loading 9p kernel modules..."
		SCRIPTDIR=$(dirname $0)
		insmod $SCRIPTDIR/9pnet.ko
		insmod $SCRIPTDIR/9pnet_virtio.ko
		insmod $SCRIPTDIR/9p.ko

		echo "Mounting 9p y2logs share to /var/log/YaST2..."
		mount -t 9p -o trans=virtio,version=9p2000.L y2logs /var/log/YaST2

		echo "Touching /var/log/YaST2/DUD_done to inform VM host's monitoring..."
		touch /var/log/YaST2/DUD_done

		echo "*** virtinsttest DUD update.pre done ***"
		""")

		self.logger.info("- Extracting 9p.ko, 9pnet.ko and 9pnet_virtio.ko from kernel-default RPM...")
		modextractdir = os.path.join(tempdir, "modextract")
		os.mkdir(modextractdir, 0755)
		cmd = "cd {0} && " \
			  "rpm2cpio {1}/suse/x86_64/kernel-default-[0123456789]*.rpm | " \
			  "cpio --quiet -imd */9p.ko */9pnet.ko */9pnet_virtio.ko"
		cmd = cmd.format(modextractdir, path)
		subprocess.check_call(cmd, shell=True)
		cmd = "find {0} -name *.ko -exec mv {{}} {1}/linux/suse/x86_64-{2}/install/ \;"
		cmd = cmd.format(modextractdir, duddir, self.osversion)
		subprocess.check_call(cmd, shell=True)

		self.logger.info("- Generating DUD archive...")
		cmd = "cd {0} && " \
			  "find | " \
			  "cpio --quiet -o >{1}/dud_opensuse{2}.cpio"
		cmd = cmd.format(duddir, tempdir, self.osversion)
		subprocess.check_call(cmd, shell=True)
		cmd = "gzip -q {0}/dud_opensuse{1}.cpio"
		cmd = cmd.format(tempdir, self.osversion)
		subprocess.check_call(cmd, shell=True)

		self.logger.info("- Removing temporary directories...")
		shutil.rmtree(modextractdir)
		shutil.rmtree(duddir)

		return "{0}/dud_opensuse{1}.cpio.gz".format(tempdir, self.osversion)

	def getVirtInstallFilesystemArgs(self):
		""" Returns a dictionary of "--filesystem" arguments for the
		virt-install command.

		The host's source directory is the key, the guest's target
		point the value.

		:rtype: dict """

		return {
			self.y2logs_dir: "y2logs"
		}

	def getVirtInstallInitrdInjectArgs(self):
		""" Returns a list of "--initrd-inject" arguments for the
		virt-install command.

		:rtype: list """

		return [
			self.dudfile
		]

	def getVirtInstallExtraArgs(self):
		""" Returns a list of "--extra-args" arguments for the
		virt-install command.

		:rtype: array """

		return [
			"y2debug=1",
			"driverupdate=file:///{0}".format(os.path.basename(self.dudfile))
		]

	def Y2LogFileReadable(self, logmsg, logname):
		""" Test method that tests whether a YaST2 logfile is readable.

		logmsg: The string to return if "logname" is readable
		logname: The logfile (in the y2log dir) to test for readability

		:rtype: string|None """

		if os.access(os.path.join(self.y2logs_dir, logname), os.R_OK):
			return logmsg
		else:
			return None

	def CatY2Log(self):
		""" Data generation method that returns tuples (lineno, line)
		    from y2log.

		Takes advantage of the generator pattern. Also handles y2log
		deletion/recreation gracefully.

		:rtype: tuple """

		y2log_name = os.path.join(self.y2logs_dir, "y2log")

		# Get y2log's current inode
		try:
			curino = os.stat(y2log_name).st_ino
		except OSError:
			return

		# Need to (re)open y2log?
		if not hasattr(self, "y2log_f") \
		or not hasattr(self, "y2log_ino") \
		or     curino != self.y2log_ino:
			if hasattr(self, "y2log_f"):
				self.y2log_f.close()
			self.y2log_f = open(y2log_name, "r")
			self.y2log_ino = os.fstat(self.y2log_f.fileno()).st_ino
			self.y2log_lineno = 0

		while True:
			line = self.y2log_f.readline()
			if not line:
				break
			self.y2log_lineno = self.y2log_lineno + 1
			yield (self.y2log_lineno, line)

	def MatchY2LogLine(self, logmsg, regexp, data):
		""" Test method that tests whether a logline matches a pattern.

		logmsg: The string to return if a match is found.
		regexp: The regular expression to match on.
		data: A tuple (lineno, line) as returned by CatY2Log.

		:rtype: string|None """

		lineno = data[0]
		line   = data[1]

		match = re.search(regexp, line)
		if match:
			return logmsg.format(
				lineno,
				match.group(1) if len(match.groups()) > 0 \
				               else None
			)
		else:
			return None

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

		if "CatY2Log" in data and data["CatY2Log"]:
			self.logbuf = self.logbuf[-3:]
			self.logbuf.append("{0}: {1}".format(data["CatY2Log"][0], data["CatY2Log"][1]))

		return self.logbuf

	def getMaxFooterDataLines(self):
		""" Returns the maximum number of lines this plugin will add
		    to the footer placed on screenshots.

		When creating the video containing the VM console's screenshots
		virtinsttest must specify the frame height beforehand. Therefore
		a plugin that implements the getFooterDataForScreenshot() method
		must also specify the maximum number of text lines (= list
		elements) that method will return.

		:rtype: integer """

		return 3

	def getStats(self, data):
		""" Get statistics about data processing in virtinsttest.

		Plugins may use timing information and the information in "data"
		to generate statistics about virtinsttest's data processing, eg. the
		number of logfile lines processed per second.

		"data" is a dictionary with the data returned by all of the
		plugin's data generation functions for the current installation
		state. It is indexed by the generation function name.

		:rtype: string A log message with statistics """

		if "CatY2Log" in data and data["CatY2Log"]:
			curlineno = data["CatY2Log"][0]
			now = time.time()
			if self.laststatstime:
				curlps = int((curlineno - self.lastlineno)/(now - self.laststatstime))
				if self.min_lps == 0 or curlps < self.min_lps:
					self.min_lps = curlps
				if curlps > self.max_lps:
					self.max_lps = curlps
				self.lps_samples = self.lps_samples+1
				self.avg_lps = int((self.avg_lps + curlps)/2)

				logmsg = "Log lines processed: cur={0}, min={1}, avg={2} lps (n={3}), max={4}".format(
					curlps,
					self.min_lps,
					self.avg_lps,
					self.lps_samples,
					self.max_lps
				)
			else:
				logmsg = None

			self.lastlineno = curlineno
			self.laststatstime = now

			return logmsg

		return None
