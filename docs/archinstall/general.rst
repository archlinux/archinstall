.. _archinstall.helpers:

.. warning::
	All these helper functions are mostly, if not all, related to outside-installation-instructions. Meaning the calls will affect your current running system - and not touch your installed system.

Profile related helpers
=======================

.. autofunction:: archinstall.list_profiles

Packages
========

.. autofunction:: archinstall.find_package

.. autofunction:: archinstall.find_packages

Locale related
==============

.. autofunction:: archinstall.list_keyboard_languages

.. autofunction:: archinstall.search_keyboard_layout

.. autofunction:: archinstall.set_keyboard_language

.. 
	autofunction:: archinstall.Installer.set_keyboard_layout

Services
========

.. autofunction:: archinstall.service_state

Mirrors
=======

.. autofunction:: archinstall.filter_mirrors_by_region

.. autofunction:: archinstall.add_custom_mirrors

.. autofunction:: archinstall.insert_mirrors

.. autofunction:: archinstall.use_mirrors

.. autofunction:: archinstall.re_rank_mirrors

.. autofunction:: archinstall.list_mirrors

Disk related
============

.. autofunction:: archinstall.BlockDevice

.. autofunction:: archinstall.Partition

.. autofunction:: archinstall.Filesystem

.. autofunction:: archinstall.device_state

.. autofunction:: archinstall.all_blockdevices

Luks (Disk encryption)
======================

.. autofunction:: archinstall.luks2

Networking
==========

.. autofunction:: archinstall.get_hw_addr

.. autofunction:: archinstall.list_interfaces

.. autofunction:: archinstall.check_mirror_reachable

.. autofunction:: archinstall.update_keyring

.. autofunction:: archinstall.enrich_iface_types

.. autofunction:: archinstall.get_interface_from_mac

.. autofunction:: archinstall.wireless_scan

.. autofunction:: archinstall.get_wireless_networks

General
=======

.. autofunction:: archinstall.log

.. autofunction:: archinstall.locate_binary

.. autofunction:: archinstall.SysCommand

.. autofunction:: archinstall.SysCommandWorker

Exceptions
==========

.. autofunction:: archinstall.RequirementError

.. autofunction:: archinstall.DiskError

.. autofunction:: archinstall.ProfileError

.. autofunction:: archinstall.SysCallError

.. autofunction:: archinstall.ProfileNotFound

.. autofunction:: archinstall.HardwareIncompatibilityError

.. autofunction:: archinstall.PermissionError

.. autofunction:: archinstall.UserError

.. autofunction:: archinstall.ServiceException
