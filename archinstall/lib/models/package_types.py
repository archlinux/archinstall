from enum import StrEnum, auto
from typing import Final

from archinstall.lib.translationhandler import tr


class Kernel(StrEnum):
	LINUX = auto()
	LINUX_LTS = 'linux-lts'
	LINUX_ZEN = 'linux-zen'
	LINUX_HARDENED = 'linux-hardened'
	LINUX_RT = 'linux-rt'
	LINUX_RT_LTS = 'linux-rt-lts'


DEFAULT_KERNEL: Final = Kernel.LINUX


class InstallationPackage(StrEnum):
	ALSA_FIRMWARE = 'alsa-firmware'
	COSMIC_GREETER = 'cosmic-greeter'
	CRONIE = 'cronie'
	EFIBOOTMGR = 'efibootmgr'
	GDM = 'gdm'
	GIT = 'git'
	GREETD = 'greetd'
	GRUB = 'grub'
	GRUB_BTRFS = 'grub-btrfs'
	INOTIFY_TOOLS = 'inotify-tools'
	IWD = 'iwd'
	LIBFIDO2 = 'libfido2'
	LIGHTDM = 'lightdm'
	LIGHTDM_GTK_GREETER = 'lightdm-gtk-greeter'
	LIGHTDM_SLICK_GREETER = 'lightdm-slick-greeter'
	LIMINE = 'limine'
	LVM2 = 'lvm2'
	LY = 'ly'
	NANO = 'nano'
	NETWORK_MANAGER_APPLET = 'network-manager-applet'
	NETWORKMANAGER = 'networkmanager'
	PAM_U2F = 'pam-u2f'
	PLASMA_LOGIN_MANAGER = 'plasma-login-manager'
	PLYMOUTH = 'plymouth'
	REFIND = 'refind'
	SDDM = 'sddm'
	SNAPPER = 'snapper'
	SOF_FIRMWARE = 'sof-firmware'
	TERMINUS_FONT = 'terminus-font'
	TIMESHIFT = 'timeshift'
	WGET = 'wget'
	WPA_SUPPLICANT = 'wpa_supplicant'
	XORG_SERVER = 'xorg-server'
	XORG_XINIT = 'xorg-xinit'
	ZRAM_GENERATOR = 'zram-generator'


class FirmwareOptdep(StrEnum):
	"""
	The optional dependencies of linux-firmware.

	The metapackage installs its hard dependencies only, so these blobs are
	never present on the target unless they are requested explicitly.
	"""

	LIQUIDIO = 'linux-firmware-liquidio'
	MARVELL = 'linux-firmware-marvell'
	MELLANOX = 'linux-firmware-mellanox'
	NFP = 'linux-firmware-nfp'
	QCOM = 'linux-firmware-qcom'
	QLOGIC = 'linux-firmware-qlogic'

	def description(self) -> str:
		match self:
			case FirmwareOptdep.LIQUIDIO:
				return tr('Cavium LiquidIO server adapters')
			case FirmwareOptdep.MARVELL:
				return tr('Marvell devices')
			case FirmwareOptdep.MELLANOX:
				return tr('Mellanox Spectrum switches')
			case FirmwareOptdep.NFP:
				return tr('Netronome Flow Processors')
			case FirmwareOptdep.QCOM:
				return tr('Qualcomm SoCs')
			case FirmwareOptdep.QLOGIC:
				return tr('QLogic devices')
