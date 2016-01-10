#!/usr/bin/python
# encoding: utf-8
#
# virtinsttest - Virtual installation testing script
# Plugin for openSUSE 13.2 (and newer)
#
# Copyright (c) 2015 Pieter Hollants <pieter@hollants.com>
# Licensed under the GNU Public License (GPL) version 3.
#

import os, re, subprocess, shutil

from plugins import *

class OpenSUSE13xPlugin(VirtInstTestPlugin):
	def __init__(self, path, tempdir):
		VirtInstTestPlugin.__init__(self, path, tempdir)

		# The most robust way to detect a openSUSE distribution seems
		# to be via the installation medium's bootloader menu
		try:
			self.osversion = None
			gfxbootfile = os.path.join(path, "boot/x86_64/loader/gfxboot.cfg")
			with open(gfxbootfile) as f:
				for line in f:
					match = re.match(r"^product=openSUSE (.+)$", line)
					if match and match.group(1):
						self.osversion = match.group(1)
						break
		except IOError as e:
			pass

		# No openSUSE medium?
		if not self.osversion:
			raise VirtInstTestPlugin.UnsupportedOS()

		# Report detected openSUSE version
		msg = "Detected openSUSE version: {0}".format(self.osversion)
		self.logger.info(msg)

		# Make detected version available via variables used by
		# standard getters
		self.osvariant = "opensuse{0}".format(re.sub("\..*", "", self.osversion))

		# For openSUSE distributions, installation monitoring will be
		# done by observing YaST's logfiles, for which we need a
		# "y2logs" directory that will be shared between host and guest
		self.logger.info("Creating \"y2logs\" directory (will be shared with VM via 9p)...")
		self.y2logs_dir = os.path.join(tempdir, "y2logs")
		os.mkdir(self.y2logs_dir)

		# openSUSE installation media lack the 9p kernel modules
		# required for sharing directories between host and guest, so
		# we retrofit them via the "Driver Update Disk" (DUD) mechanism
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

		self.dudfile = "{0}/dud_opensuse{1}.cpio.gz".format(tempdir, self.osversion)

		self.logger.info("- Removing temporary directories...")
		shutil.rmtree(modextractdir)
		shutil.rmtree(duddir)

	def getFilesystems(self):
		return {
			self.y2logs_dir: "y2logs"
		}

	def getInitrdInjects(self):
		return [
			self.dudfile
		]

	def getExtraArgs(self):
		return [
			"y2debug=1",
			"driverupdate=file:///{0}".format(os.path.basename(self.dudfile))
		]

	def Y2LogFileReadable(self, logmsg, logname):
		if os.access(os.path.join(self.y2logs_dir, logname), os.R_OK):
			return logmsg
		else:
			return None

	# Generator function that returns a tuple (lineno, line) from y2log.
	# Also handles file deletion/recreation gracefully.
	def CatY2Log(self):
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

	def MatchY2LogLine(self, logmsg, pattern, data):
		lineno = data[0]
		line   = data[1]

		match = re.search(pattern, line)
		if match:
			return logmsg.format(lineno, match.group(1) if len(match.groups())>0 else None)
		else:
			return None
