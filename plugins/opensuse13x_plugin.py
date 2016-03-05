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
		if self.osversion.startswith("Leap "):
			self.osvariant = "opensuse-factory"
		else:
			self.osvariant = "opensuse{0}".format(self.osversion)
		self.logger.debug("Deduced osvariant: {0}".format(self.osvariant))

		# For openSUSE distributions, installation monitoring will be
		# done by observing YaST's logfiles, for which we need a
		# "y2logs" directory that will be shared between host and guest
		self.logger.info("Creating \"y2logs\" directory (will be shared with VM via 9p)...")
		self.y2logs_dir = os.path.join(tempdir, "y2logs")
		os.mkdir(self.y2logs_dir)

		# Remember arguments for prepareInstallation()
		self.path    = path
		self.tempdir = tempdir

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

	def prepareInstallation(self):
		# openSUSE installation media lack the 9p kernel modules
		# required for sharing directories between host and guest, so
		# we retrofit them via the "Driver Update Disk" (DUD) mechanism
		self.logger.info("Creating Driver Update Disk (DUD) image to retrofit 9p filesystem sharing:")

		# Workaround for Tumbleweed
		osversion = "13.2" if self.osversion.startswith("Leap") \
		                   else self.osversion

		self.logger.info("- Creating DUD directory structure...")
		duddir = os.path.join(self.tempdir, "dud")
		dudinstalldir = os.path.join(
			duddir,
			"linux/suse/x86_64-{0}/install".format(osversion)
		)
		os.makedirs(dudinstalldir, 0755)

		self.logger.info("- Creating dud.config...")
		with open(os.path.join(duddir, "dud.config"), "w") as f:
			f.write("UpdateName: virtinsttest DUD for openSUSE {0}\n".format(osversion))
			f.write("UpdateID: e82ffff3-34d9-4f6b-bd58-b638f234776\n")

		self.logger.info("- Creating DUD update.pre script...")
		with open(
			os.path.join(
				duddir,
				"linux/suse/x86_64-{0}/install/update.pre".format(osversion)
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
		modextractdir = os.path.join(self.tempdir, "modextract")
		os.mkdir(modextractdir, 0755)
		cmd = "cd {0} && " \
			  "rpm2cpio {1}/suse/x86_64/kernel-default-[0123456789]*.rpm | " \
			  "cpio --quiet -imd */9p.ko */9pnet.ko */9pnet_virtio.ko"
		cmd = cmd.format(modextractdir, self.path)
		subprocess.check_call(cmd, shell=True)
		cmd = "find {0} -name *.ko -exec mv {{}} {1}/linux/suse/x86_64-{2}/install/ \;"
		cmd = cmd.format(modextractdir, duddir, osversion)
		subprocess.check_call(cmd, shell=True)

		self.logger.info("- Generating DUD archive...")
		cmd = "cd {0} && " \
			  "find | " \
			  "cpio --quiet -o >{1}/dud_opensuse{2}.cpio"
		cmd = cmd.format(duddir, self.tempdir, osversion)
		subprocess.check_call(cmd, shell=True)
		cmd = "gzip -q {0}/dud_opensuse{1}.cpio"
		cmd = cmd.format(self.tempdir, osversion)
		subprocess.check_call(cmd, shell=True)

		self.logger.info("- Removing temporary directories...")
		shutil.rmtree(modextractdir)
		shutil.rmtree(duddir)

		self.dudfile = "{0}/dud_opensuse{1}.cpio.gz".format(self.tempdir, osversion)

	def getVirtInstallFilesystemArgs(self):
		return {
			self.y2logs_dir: "y2logs"
		}

	def getVirtInstallInitrdInjectArgs(self):
		return [
			self.dudfile
		]

	def getVirtInstallExtraArgs(self):
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
		if "CatY2Log" in data and data["CatY2Log"]:
			self.logbuf = self.logbuf[-3:]
			self.logbuf.append("{0}: {1}".format(data["CatY2Log"][0], data["CatY2Log"][1]))

		return self.logbuf

	def getMaxFooterDataLines(self):
		return 3

	def getStats(self, data):
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
