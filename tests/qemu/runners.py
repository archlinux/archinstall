import threading
import time
import logging
import asyncio
from testbase import TestBase

logger = logging.getLogger("archtest")

class TestLeaveAllDefault(TestBase):
	def __init__(self, serial_monitor):
		super().__init__(serial_monitor)
		self.running_test = False
		self.installation_complete = False
		self.installation_successful = False
		self.fix_post_install_boot = False
		self.entered_disk_enc_pw = False

		self.exit_code = -1

		threading.Thread.__init__(self)
		self.start()

	def run(self):
		while True:
			if b'Set/Modify the below options' in self.buffer and self.running_test is False:
				# This is our entrypoint, from here on we'll have to fly blind because
				# the menu system uses ANSI/VT100 escape codes to put the arrow and stuff.
				# So we can't check for `> Archinstall langauge` for instance.
				# So lets fire away our test sequence and monitor for some break-point values.
				logger.info(f"Running through a typical installation scenario accepting all defaults.")
				self.running_test = True
				time.sleep(1)

				logger.info(f"Selecting a good regional mirror")
				# Navigate to Mirror selection
				self.send_key('arrow_down', delay=0.2)
				self.send_key('enter', delay=0.2)
				self.send_key('enter', delay=0.2)
				time.sleep(2) # Let the UI buffer complete before we start searching
				# Search for a known mirror region with good speed relative to source of execution
				self.send_key('/', delay=0.2)
				self.send_string('Sweden', delay=0.2)
				self.send_key('enter', delay=0.2)
				# Exit the mirror selection screen
				self.send_key('arrow_down', delay=0.2)
				self.send_key('arrow_down', delay=0.2)
				self.send_key('enter', delay=0.2)
				# Enter 'locale' option
				logger.info(f"Setting a keyboard locale to something known")
				self.send_key('enter', delay=0.2)
				# Enter keyboard layout
				self.send_key('enter', delay=0.2)
				time.sleep(1) # Let the UI buffer complete again before searching
				self.send_key('/', delay=0.2)
				time.sleep(0.5)
				self.send_string('sv-latin1', delay=0.2)
				self.send_key('enter', delay=0.2)
				# Exit locale
				logger.info(f"Selecting the one virtual harddrive")
				self.send_key('arrow_down', delay=0.2)
				self.send_key('arrow_down', delay=0.2)
				self.send_key('arrow_down', delay=0.2)
				self.send_key('enter', delay=0.2)
				# Enter disk config
				self.send_key('enter', delay=0.2)
				# Enter partitioning
				self.send_key('enter', delay=0.2)
				# Use best effort
				self.send_key('enter', delay=0.2)
				# Select second option, which should be Virtio Block Device
				self.send_key('arrow_down', delay=0.2)
				self.send_key('enter', delay=0.2)
				# Select btrfs
				logger.info(f"Selecting btrfs + subvolumes + compression")
				self.send_key('enter', delay=0.2)
				# Use subvolumes
				self.send_key('enter', delay=0.2)
				# Use compression
				self.send_key('enter', delay=0.2)
				# Exit partitioning
				logger.info(f"Setting disk encryption password")
				self.send_key('arrow_down', delay=0.2)
				self.send_key('arrow_down', delay=0.2)
				self.send_key('enter', delay=0.2)
				# Enter disk encryption
				self.send_key('enter', delay=0.2)
				# Select encryption type
				self.send_key('enter', delay=0.2)
				# Select LUKS
				self.send_key('enter', delay=0.2)
				# Enter password selection
				self.send_key('arrow_down', delay=0.2)
				self.send_key('enter', delay=0.2)
				# Enter a test password
				self.send_string('test', delay=0.2)
				self.send_key('enter', delay=0.2)
				self.send_string('test', delay=0.2)
				self.send_key('enter', delay=0.2)
				# Select partition
				self.send_key('arrow_down', delay=0.2)
				self.send_key('arrow_down', delay=0.2)
				self.send_key('enter', delay=0.2)
				# Select the default partition
				self.send_key('enter', delay=0.2)
				# Exit encryption menu
				self.send_key('arrow_down', delay=0.2)
				self.send_key('arrow_down', delay=0.2)
				self.send_key('arrow_down', delay=0.2)
				self.send_key('arrow_down', delay=0.2)
				self.send_key('enter', delay=0.2)
				# Skip some entries in the main menu
				logger.info(f"Setting a root password")
				self.send_key('arrow_down', delay=0.2)
				self.send_key('arrow_down', delay=0.2)
				self.send_key('arrow_down', delay=0.2)
				self.send_key('arrow_down', delay=0.2) # Move to "root password"
				self.send_key('enter', delay=0.2)
				# Enter a test root password
				self.send_string('test', delay=0.2)
				self.send_key('enter', delay=0.2)
				self.send_string('test', delay=0.2)
				self.send_key('enter', delay=0.2)
				# Skip some entries
				logger.info(f"Adding nano as additional password")
				self.send_key('arrow_down', delay=0.2)
				self.send_key('arrow_down', delay=0.2)
				self.send_key('arrow_down', delay=0.2)
				self.send_key('arrow_down', delay=0.2) # Additional packages
				self.send_key('enter', delay=0.2)
				# Enter a test package that is reliable
				self.send_string('nano', delay=0.2)
				self.send_key('enter', delay=0.2)
				logger.info(f"Setting network config")
				# Configure networking
				time.sleep(1)
				self.send_key('enter', delay=0.2)
				self.send_key('enter', delay=0.2)
				time.sleep(2)
				# Proceed to installation
				logger.info(f"Proceeding to install")
				self.send_key('arrow_down', delay=0.2)
				self.send_key('arrow_down', delay=0.2)
				self.send_key('arrow_down', delay=0.2)
				self.send_key('arrow_down', delay=0.2) # Install
				self.send_key('enter', delay=0.2)
				# Proceed to install
				self.send_key('enter', delay=0.2)
			elif b'Would you like to chroot' in self.buffer and self.installation_complete is False:
				logger.info(f"Installation appears to have completed")
				self.installation_complete = True
				self.send_key('arrow_down', delay=0.2) # No
				self.send_key('enter', delay=0.2)
			elif b'Installation completed without any errors' in self.buffer and self.installation_successful is False:
				logger.info(f"Installation was successful, rebooting")
				self.installation_successful = True
				self.send_string('reboot', delay=0.2)
				self.send_key('enter', delay=0.2)
			elif b'Arch Linux (linux-fallback)' in self.buffer and self.installation_successful is True and self.fix_post_install_boot is False:
				logger.info(f"Found linux-fallback, assuming bootloader needs adjusting for serial output")
				self.fix_post_install_boot = True
				asyncio.run_coroutine_threadsafe(self.serial_monitor.edit_boot(), loop=self.serial_monitor.QMP.loop)
			elif b'A password is required to access the root volume' in self.buffer and self.installation_successful is True and self.fix_post_install_boot is True and self.entered_disk_enc_pw is False:
				logger.info(f"Found disk encryption password, supplying it")
				self.entered_disk_enc_pw = True
				self.send_string('test', delay=0.2)
				self.send_key('enter', delay=0.2)
			elif b'archlinux login:' in self.buffer[-500:] and self.installation_successful and self.entered_disk_enc_pw:
				logger.info("Installation successful, for real!")
				self.exit_code = 0
				break

			time.sleep(0.25)