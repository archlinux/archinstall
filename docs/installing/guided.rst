.. _guided:

Guided installation
===================

| This is the default script the Arch Linux `Archinstall package <https://archlinux.org/packages/extra/any/archinstall/>`_.
| It will guide you through a very basic installation of Arch Linux.

.. note::
    There are other scripts and they can be invoked by executing `archinstall <script>` *(without .py)*. To see a complete list of scripts, see the source code directory `examples/ <https://github.com/archlinux/archinstall/tree/master/examples>`_

The installer has three pre-requisites:
 * The latest version of `Arch Linux ISO <https://archlinux.org/download/>`_
 * A physical or virtual machine to install on
 * A `working internet connection <https://wiki.archlinux.org/title/installation_guide#Connect_to_the_internet>`_ prior to running archinstall

.. note::
    A basic understanding of machines, ISO-files and command line arguments are needed.
    Please read the official `Arch Linux Wiki <https://wiki.archlinux.org/>`_ to learn more about your future operating system.

.. warning::
    The installer will not configure WiFi before the installation begins. You need to read up on `Arch Linux networking <https://wiki.archlinux.org/index.php/Network_configuration>`_ before you continue.

Running the guided installation
-------------------------------

To start the installer, run the following in the latest Arch Linux ISO:

.. code-block:: sh

    archinstall --script guided
    
| The ``--script guided`` argument is optional as it's the default behavior.
| But this will use our most guided installation and if you skip all the option steps it will install a minimal Arch Linux experience.

Installing directly from a configuration file
---------------------------------------------

| The guided installation also supports installing with pre-configured answers to all the guided steps.
| This can be a quick and convenient way to re-run one or several installations.
|
| After each successful installation a pre-configured configuration will be found at ``/var/log/archinstall`` both on the live media and the installed system.

There are three different configuration files, all of which are optional.
 * ``--config`` that deals with the general configuration of language and which profiles to use.
 * ``--creds`` which takes any ``superuser``, ``user`` or ``root`` account data.
 * ``--disk_layouts`` for defining the desired partition strategy on the selected ``"harddrives"`` in ``--config``.

.. note::
    You can always get the latest options with ``archinstall --dry-run``, but edit the following json according to your needs.
    Save the configuration as a ``.json`` file. Archinstall can source it via a local or remote path (URL)
    
.. code-block:: json

    {
        "audio": "pipewire",
        "bootloader": "systemd-bootctl",
        "custom-commands": [
            "cd /home/devel; git clone https://aur.archlinux.org/paru.git",
            "chown -R devel:devel /home/devel/paru",
            "usermod -aG docker devel"
        ],
        "filesystem": "btrfs",
        "gfx_driver": "VMware / VirtualBox (open-source)",
        "harddrives": [
            "/dev/nvme0n1"
        ],
        "swap": true,
        "hostname": "development-box",
        "kernels": [
            "linux"
        ],
        "keyboard-language": "us",
        "mirror-region": "Worldwide",
        "nic": {
            "type": "NM"
        },
        "ntp": true,
        "packages": ["docker", "git", "wget", "zsh"],
        "profile": "gnome",
        "services": ["docker"],
        "sys-encoding": "utf-8",
        "sys-language": "en_US",
        "timezone": "US/Eastern",
    }

To use it, assuming you put it on ``https://domain.lan/config.json``:

.. code-block:: sh

    archinstall --config https://domain.lan/config.json

Options for ``--config``
------------------------

*(To see which keys are required, scroll to the right in the above table.)*

+----------------------+--------------------------------------------------------+---------------------------------------------------------------------------------------------+-----------------------------------------------+
|         Key          |                 Values                                 |                                     Description                                             |                   Required                    |
|                      |                                                        |                                                                                             |                                               |
+======================+========================================================+=============================================================================================+===============================================+
| audio                | pipewire/pulseaudio                                    | Audioserver to be installed                                                                 | No                                            |
+----------------------+--------------------------------------------------------+---------------------------------------------------------------------------------------------+-----------------------------------------------+
| bootloader           | systemd-bootctl/grub-install                           | Bootloader to be installed *(grub being mandatory on BIOS machines)*                        | Yes                                           |
+----------------------+--------------------------------------------------------+---------------------------------------------------------------------------------------------+-----------------------------------------------+
| custom-commands      | [ <command1>, <command2>, ...]                         | Custom commands to be run post install                                                      | No                                            |
+----------------------+--------------------------------------------------------+---------------------------------------------------------------------------------------------+-----------------------------------------------+
| gfx_driver           | - "VMware / VirtualBox (open-source)"                  | Graphics Drivers to install                                                                 | No                                            |
|                      | - "Nvidia"                                             |                                                                                             |                                               |
|                      | - "Intel (open-source)"                                |                                                                                             |                                               |
|                      | - "AMD / ATI (open-source)"                            |                                                                                             |                                               |
|                      | - "All open-source (default)"                          |                                                                                             |                                               |
+----------------------+--------------------------------------------------------+---------------------------------------------------------------------------------------------+-----------------------------------------------+
| harddrives           | [ <path of device>, <path of second device>, ... }     | Multiple paths to block devices to be formatted                                             | No[1]                                         |
+----------------------+--------------------------------------------------------+---------------------------------------------------------------------------------------------+-----------------------------------------------+
| hostname             | any                                                    | Hostname of machine after installation. Default will be ``archinstall``                     | No                                            |
+----------------------+--------------------------------------------------------+---------------------------------------------------------------------------------------------+-----------------------------------------------+
| kernels              | [ "kernel1", "kernel2"]                                | List of kernels to install eg: linux, linux-lts, linux-zen  etc                             | At least 1                                     |
+----------------------+--------------------------------------------------------+---------------------------------------------------------------------------------------------+-----------------------------------------------+
| keyboard-language    | Any valid layout given by ``localectl list-keymaps``   | eg: ``us``, ``de`` or ``de-latin1`` etc. Defaults to ``us``                                 | No                                            |
+----------------------+--------------------------------------------------------+---------------------------------------------------------------------------------------------+-----------------------------------------------+
| mirror-region        | | {"<Region Name>": { "Mirror URL": True/False}, ..}   | | Defaults to automatic selection.                                                          | No                                            |
|                      | | "Worldwide" or "Sweden"                              | | Either takes a dictionary structure of region and a given set of mirrors.                 |                                               |
|                      |                                                        | | Or just a region and archinstall will source any mirrors for that region automatically    |                                               |
+----------------------+--------------------------------------------------------+---------------------------------------------------------------------------------------------+-----------------------------------------------+
| nic                  | | { type: <ISO|NM|MANUAL> }                            | | Type must be one of ISO, NM, MANUAL. ISO will copy the configuration on the image,        | No                                            |
|                      | |                                                      | | NM configures NetworkManager and MANUAL allows to specify custom configuration            |                                               |
|                      | | { "iface": "eth0"}                                   | | Only MANUAL: name of the interface                                                        |                                               |
|                      | | { "dhcp": <boolean>}                                 | | Only MANUAL: If set to true DHCP auto will be setup and all further configs ignored       |                                               |
|                      | | { "ip": <ip>}                                        | | Only MANUAL: Ip address to set, is MANDATORY                                              |                                               |
|                      | | { "gateway": <ip>}                                   | | Only MANUAL: Optional gateway                                                             |                                               |
|                      | | { "dns": [<ip>]}                                     | | Only MANUAL: Optional DNS servers                                                         |                                               |
+----------------------+--------------------------------------------------------+---------------------------------------------------------------------------------------------+-----------------------------------------------+
| ntp                  | <boolean>                                              | Set to true to set-up ntp post install                                                      | No                                            |
+----------------------+--------------------------------------------------------+---------------------------------------------------------------------------------------------+-----------------------------------------------+
| packages             | [ "package1", "package2", ..]                          | List of packages to install post-installation                                               | No                                            |
+----------------------+--------------------------------------------------------+---------------------------------------------------------------------------------------------+-----------------------------------------------+
| profile              | Name of the profile to install                         | Profiles are present in                                                                     | No                                            |
|                      |                                                        | `profiles/ <https://github.com/archlinux/archinstall/tree/master/profiles>`_,               |                                               |
|                      |                                                        | use the name of a profile to install it without the ``.py`` extension.                      |                                               |
+----------------------+--------------------------------------------------------+---------------------------------------------------------------------------------------------+-----------------------------------------------+
| services             | [ "service1", "service2", ..]                          | Services to enable post-installation                                                        | No                                            |
+----------------------+--------------------------------------------------------+---------------------------------------------------------------------------------------------+-----------------------------------------------+
| sys-encoding         | "utf-8"                                                | Set to change system encoding post-install, ignored if --advanced flag is not passed        | No                                            |
+----------------------+--------------------------------------------------------+---------------------------------------------------------------------------------------------+-----------------------------------------------+
| sys-language         | "en_US"                                                | Set to change system language post-install, ignored if --advanced flag is not passed        | No                                            |
+----------------------+--------------------------------------------------------+---------------------------------------------------------------------------------------------+-----------------------------------------------+
| timezone             | Timezone to configure in installation                  | Timezone eg: UTC, Asia/Kolkata etc. Defaults to UTC                                         | No                                            |
+----------------------+--------------------------------------------------------+---------------------------------------------------------------------------------------------+-----------------------------------------------+

.. note::
    [1] If no entries are found in ``harddrives``, archinstall guided installation will use whatever is mounted currently under ``/mnt/archinstall``.

Options for ``--creds``
-----------------------

| Creds is a separate configuration file to separate normal options from more sensitive data like passwords.
| Below is an example of how to set the root password and below that are description of other values that can be set.

.. code-block:: json

    {
        "!root-password" : "SecretSanta2022"
    }

+----------------------+--------------------------------------------------------+--------------------------------------------------------------------------------------+-----------------------------------------------+
|         Key          |                 Values                                 |                                     Description                                      |                   Required                    |
+======================+========================================================+======================================================================================+===============================================+
| !encryption-password | any                                                    | Password to encrypt disk, not encrypted if password not provided                     | No                                            |
+----------------------+--------------------------------------------------------+--------------------------------------------------------------------------------------+-----------------------------------------------+
| !root-password       | any                                                    | The root account password                                                            | No                                            |
+----------------------+--------------------------------------------------------+--------------------------------------------------------------------------------------+-----------------------------------------------+
| !users               | { "username": "<USERNAME>"                             | List of regular user credentials, see configuration for reference                    | No                                            |
|                      |   "!password": "<PASSWORD>",                           |                                                                                      |                                               |
|                      |   "sudo": false|true}                                  |                                                                                      |                                               |
+----------------------+--------------------------------------------------------+--------------------------------------------------------------------------------------+-----------------------------------------------+

.. note::
    [1] ``!users`` is optional only if ``!root-password`` was set. ``!users`` will be enforced otherwise and the minimum amount of users with sudo privileges required will be set to 1.

Options for ``--disk_layouts``
------------------------------

.. note::
    | The layout of ``--disk_layouts`` is a bit complicated.
    | It's highly recommended that you generate it using ``--dry-run`` which will simulate an installation, without performing any damaging actions on your machine. *(no formatting is done)*

.. code-block:: json

    {
        "/dev/loop0": {
            "partitions": [
                {
                    "boot": true,
                    "encrypted": false,
                    "filesystem": {
                        "format": "fat32"
                    },
                    "wipe": true,
                    "mountpoint": "/boot",
                    "size": "513MB",
                    "start": "5MB",
                    "type": "primary"
                },
                {
                    "btrfs": {
                        "subvolumes": {
                            "@.snapshots": "/.snapshots",
                            "@home": "/home",
                            "@log": "/var/log",
                            "@pkgs": "/var/cache/pacman/pkg"
                        }
                    },
                    "encrypted": true,
                    "filesystem": {
                        "format": "btrfs"
                    },
                    "wipe": true,
                    "mountpoint": "/",
                    "size": "100%",
                    "start": "518MB",
                    "type": "primary"
                }
            ],
            "wipe": true
        }
    }

| The overall structure is that of ``{ "blockdevice-path" : ...}`` followed by options for that blockdevice.
| Each partition has it's own settings, and the formatting is executed in order *(top to bottom in the above example)*.
| Mountpoints is later mounted in order of path traversal, ``/`` before ``/home`` etc.

+----------------------+-----------------------------------------------------+--------------------------------------------------------------------------------------+-----------------------------------------------+
|         Key          |                 Values                              |                                     Description                                      |                   Required                    |
|                      |                                                     |                                                                                      |                                               |
+======================+=====================================================+======================================================================================+===============================================+
| filesystem           | { "format": "ext4 / btrfs / fat32 etc." }           | Filesystem for root and other partitions                                             | Yes                                           |
+----------------------+-----------------------------------------------------+--------------------------------------------------------------------------------------+-----------------------------------------------+
| boot                 | <bool>                                              | Marks the partition as bootable                                                      | No                                            |
+----------------------+-----------------------------------------------------+--------------------------------------------------------------------------------------+-----------------------------------------------+
| encrypted            | <bool>                                              | Mark the partition for encryption                                                    | No                                            |
+----------------------+-----------------------------------------------------+--------------------------------------------------------------------------------------+-----------------------------------------------+
| mountpoint           | /path                                               | Relative to the inside of the installation, where should the partition be mounted    | Yes                                           |
+----------------------+-----------------------------------------------------+--------------------------------------------------------------------------------------+-----------------------------------------------+
| start                | <size><B, MiB, GiB, %, etc>                         | The start position of the partition                                                  | Yes                                           |
+----------------------+-----------------------------------------------------+--------------------------------------------------------------------------------------+-----------------------------------------------+
| type                 | primary                                             | Only used if MBR and BIOS is used. Marks what kind of partition it is.               | No                                            |
+----------------------+-----------------------------------------------------+--------------------------------------------------------------------------------------+-----------------------------------------------+
| btrfs                | { "subvolumes": {"subvolume": "mountpoint"}}        | Support for btrfs subvolumes for a given partition                                   | No                                            |
+----------------------+-----------------------------------------------------+--------------------------------------------------------------------------------------+-----------------------------------------------+
