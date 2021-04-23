import getpass
import time
import json
import os
import archinstall
from archinstall.lib.hardware import hasUEFI
from archinstall.lib.profiles import Profile

if hasUEFI() is False:
    archinstall.log("ArchInstall currently only supports machines booted with UEFI.\nMBR & GRUB support is coming in version 2.2.0!",
                    fg="red", level=archinstall.LOG_LEVELS.Error)
    exit(1)


def perform_installation_steps():
    print()
    print('This is your chosen configuration:')
    archinstall.log("-- Guided template chosen (with below config) --",
                    level=archinstall.LOG_LEVELS.Debug)
    archinstall.log(json.dumps(archinstall.arguments, indent=4, sort_keys=True,
                               cls=archinstall.JSON), level=archinstall.LOG_LEVELS.Info)
    print(archinstall.arguments)
    print()

    input('Press Enter to continue.')

    """
		Issue a final warning before we continue with something un-revertable.
		We mention the drive one last time, and count from 5 to 0.
	"""

    if archinstall.arguments.get('harddrive', None):
        print(
            f" ! Formatting {archinstall.arguments['harddrive']} in ", end='')
        archinstall.do_countdown()

        """
			Setup the blockdevice, filesystem (and optionally encryption).
			Once that's done, we'll hand over to perform_installation()
		"""
        with archinstall.Filesystem(archinstall.arguments['harddrive'], archinstall.GPT) as fs:
            # Wipe the entire drive if the disk flag `keep_partitions`is False.
            if archinstall.arguments['harddrive']["keep_partitions"]:
                archinstall.arguments['harddrive'].keep_partitions = True
            if archinstall.arguments['harddrive'].keep_partitions is False:
                fs.use_entire_disk(
                    root_filesystem_type=archinstall.arguments.get('filesystem', 'btrfs'))

            # Check if encryption is desired and mark the root partition as encrypted.
            if archinstall.arguments.get('!encryption-password', None):
                root_partition = fs.find_partition('/')
                root_partition.encrypted = True

            # After the disk is ready, iterate the partitions and check
            # which ones are safe to format, and format those.
            for partition in archinstall.arguments['harddrive']:
                if partition.safe_to_format():
                    # Partition might be marked as encrypted due to the filesystem type crypt_LUKS
                    # But we might have omitted the encryption password question to skip encryption.
                    # In which case partition.encrypted will be true, but passwd will be false.
                    if partition.encrypted and (passwd := archinstall.arguments.get('!encryption-password', None)):
                        partition.encrypt(password=passwd)
                    else:
                        partition.format()
                else:
                    archinstall.log(
                        f"Did not format {partition} because .safe_to_format() returned False or .allow_formatting was False.", level=archinstall.LOG_LEVELS.Debug)

            fs.find_partition('/boot').format('vfat')

            if archinstall.arguments.get('!encryption-password', None):
                # First encrypt and unlock, then format the desired partition inside the encrypted part.
                # archinstall.luks2() encrypts the partition when entering the with context manager, and
                # unlocks the drive so that it can be used as a normal block-device within archinstall.
                with archinstall.luks2(fs.find_partition('/'), 'luksloop', archinstall.arguments.get('!encryption-password', None)) as unlocked_device:
                    unlocked_device.format(fs.find_partition('/').filesystem)
                    unlocked_device.mount('/mnt')
            else:
                fs.find_partition(
                    '/').format(fs.find_partition('/').filesystem)
                fs.find_partition('/').mount('/mnt')

            fs.find_partition('/boot').mount('/mnt/boot')

    perform_installation('/mnt')


def perform_installation(mountpoint):
    """
    Performs the installation steps on a block device.
    Only requirement is that the block devices are
    formatted and setup prior to entering this function.
    """
    with archinstall.Installer(mountpoint) as installation:
        # if len(mirrors):
        # Certain services might be running that affects the system during installation.
        # Currently, only one such service is "reflector.service" which updates /etc/pacman.d/mirrorlist
        # We need to wait for it before we continue since we opted in to use a custom mirror/region.
        installation.log(f'Waiting for automatic mirror selection (reflector) to complete.',
                         level=archinstall.LOG_LEVELS.Info)
        while archinstall.service_state('reflector') not in ('dead', 'failed'):
            time.sleep(1)

        # Set mirrors used by pacstrap (outside of installation)
        if archinstall.arguments.get('mirror-region', None):
            # Set the mirrors for the live medium
            archinstall.use_mirrors(archinstall.arguments['mirror-region'])

        if installation.minimal_installation():
            installation.set_hostname(archinstall.arguments['hostname'])
            if archinstall.arguments['mirror-region'].get("mirrors", {}) != None:
                # Set the mirrors in the installation medium
                installation.set_mirrors(
                    archinstall.arguments['mirror-region'])
            installation.set_keyboard_language(
                archinstall.arguments['keyboard-language'])
            installation.add_bootloader()

            # If user selected to copy the current ISO network configuration
            # Perform a copy of the config
            if archinstall.arguments.get('nic', {}) == 'Copy ISO network configuration to installation':
                # Sources the ISO network configuration to the install medium.
                installation.copy_ISO_network_config(enable_services=True)
            elif archinstall.arguments.get('nic', {}).get('NetworkManager', False):
                installation.add_additional_packages("networkmanager")
                installation.enable_service('NetworkManager.service')
            # Otherwise, if a interface was selected, configure that interface
            elif archinstall.arguments.get('nic', {}):
                installation.configure_nic(
                    **archinstall.arguments.get('nic', {}))
                installation.enable_service('systemd-networkd')
                installation.enable_service('systemd-resolved')

            if archinstall.arguments.get('audio', None) != None:
                installation.log(
                    f"This audio server will be used: {archinstall.arguments.get('audio', None)}", level=archinstall.LOG_LEVELS.Info)
                if archinstall.arguments.get('audio', None) == 'pipewire':
                    print('Installing pipewire ...')
                    installation.add_additional_packages(
                        ["pipewire", "pipewire-alsa", "pipewire-jack", "pipewire-media-session", "pipewire-pulse", "gst-plugin-pipewire", "libpulse"])
                elif archinstall.arguments.get('audio', None) == 'pulseaudio':
                    print('Installing pulseaudio ...')
                    installation.add_additional_packages("pulseaudio")
            else:
                installation.log("No audio server will be installed.",
                                 level=archinstall.LOG_LEVELS.Info)

            if archinstall.arguments.get('packages', None) and archinstall.arguments.get('packages', None)[0] != '':
                installation.add_additional_packages(
                    archinstall.arguments.get('packages', None))

            if archinstall.arguments.get('profile', None):
                installation.install_profile(
                    archinstall.arguments.get('profile', None))

            for user, user_info in archinstall.arguments.get('users', {}).items():
                installation.user_create(
                    user, user_info["!password"], sudo=False)

            for superuser, user_info in archinstall.arguments.get('superusers', {}).items():
                installation.user_create(
                    superuser, user_info["!password"], sudo=True)

            if (timezone := archinstall.arguments.get('timezone', None)):
                installation.set_timezone(timezone)

            if (root_pw := archinstall.arguments.get('!root-password', None)) and len(root_pw):
                installation.user_set_pw('root', root_pw)

        installation.log(
            "For post-installation tips, see https://wiki.archlinux.org/index.php/Installation_guide#Post-installation", fg="yellow")
        choice = input(
            "Would you like to chroot into the newly created installation and perform post-installation configuration? [Y/n] ")
        if choice.lower() in ("y", ""):
            try:
                installation.drop_to_shell()
            except:
                pass


perform_installation_steps()
