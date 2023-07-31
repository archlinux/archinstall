.. _guided:

Guided installation
===================

Archinstall ships with a pre-programmed `Guided Installer <https://github.com/archlinux/archinstall/blob/master/archinstall/scripts/guided.py>`_ guiding you through the mandatory steps as well as some optional configurations that can be done.

.. note::

   Other pre-programmed scripts can be invoked by executing :code:`archinstall <script>` *(without .py)*. To see a complete list of scripts, see the source code directory `archinstall/scripts/ <https://github.com/archlinux/archinstall/blob/master/archinstall/scripts/>`_

.. warning::

   The installer requires the latest version of `Arch Linux ISO <https://archlinux.org/download/>`_ as well as basic understanding of how ISO's and computers work. Please read the official `Arch Linux Wiki <https://wiki.archlinux.org/>`_ to learn more about your future operating system.


.. warning::
    The installer will not configure WiFi before the installation begins. You need to read up on `Arch Linux networking <https://wiki.archlinux.org/index.php/Network_configuration>`_ before you continue.

Running the guided installation
-------------------------------

To start the installer, run the following in the latest Arch Linux ISO:

.. code-block:: sh

    archinstall

Since the guided installer is the default script, this is the equvilant of running :code:`archinstall guided`


The guided installation also supports installing with pre-configured answers to all the guided steps. This can be a quick and convenient way to re-run one or several installations.

There are two configuration files, both are optional.

``--config``
------------

This parameter takes a local or remote :code:`.json` file as argument and contains the overall configuration and menu answers for the guided installer.

.. note::

   You can always get the latest options for this file with ``archinstall --dry-run``, this executes the guided installer in a safe mode where no permanent actions will be taken on your system but simulate a run and save the configuration to disk.

Example usage
^^^^^^^^^^^^^

.. code-block:: sh

    archinstall --config https://domain.lan/config.json

The contents of :code:`https://domain.lan/config.json`:

.. code-block:: json

   {
       "__separator__": null,
       "additional-repositories": [],
       "archinstall-language": "English",
       "audio_config": null,
       "bootloader": "Systemd-boot",
       "config_version": "2.6.0",
       "debug": false,
       "disk_config": {
           "config_type": "manual_partitioning",
           "device_modifications": [
               {
                   "device": "/dev/sda",
                   "partitions": [
                       {
                           "btrfs": [],
                           "flags": [
                               "Boot"
                           ],
                           "fs_type": "fat32",
                           "length": {
                               "sector_size": null,
                               "total_size": null,
                               "unit": "B",
                               "value": 99982592
                           },
                           "mount_options": [],
                           "mountpoint": "/boot",
                           "obj_id": "369f31a8-2781-4d6b-96e7-75680552b7c9",
                           "start": {
                               "sector_size": {
                                   "sector_size": null,
                                   "total_size": null,
                                   "unit": "B",
                                   "value": 512
                               },
                               "total_size": null,
                               "unit": "sectors",
                               "value": 34
                           },
                           "status": "create",
                           "type": "primary"
                       },
                       {
                           "btrfs": [],
                           "flags": [],
                           "fs_type": "fat32",
                           "length": {
                               "sector_size": null,
                               "total_size": null,
                               "unit": "B",
                               "value": 100000000
                           },
                           "mount_options": [],
                           "mountpoint": "/efi",
                           "obj_id": "13cf2c96-8b0f-4ade-abaa-c530be589aad",
                           "start": {
                               "sector_size": {
                                   "sector_size": null,
                                   "total_size": null,
                                   "unit": "B",
                                   "value": 512
                               },
                               "total_size": {
                                   "sector_size": null,
                                   "total_size": null,
                                   "unit": "B",
                                   "value": 16106127360
                               },
                               "unit": "MB",
                               "value": 100
                           },
                           "status": "create",
                           "type": "primary"
                       },
                       {
                           "btrfs": [],
                           "flags": [],
                           "fs_type": "ext4",
                           "length": {
                               "sector_size": null,
                               "total_size": null,
                               "unit": "B",
                               "value": 15805127360
                           },
                           "mount_options": [],
                           "mountpoint": "/",
                           "obj_id": "3e75d045-21a4-429d-897e-8ec19a006e8b",
                           "start": {
                               "sector_size": {
                                   "sector_size": null,
                                   "total_size": null,
                                   "unit": "B",
                                   "value": 512
                               },
                               "total_size": {
                                   "sector_size": null,
                                   "total_size": null,
                                   "unit": "B",
                                   "value": 16106127360
                               },
                               "unit": "MB",
                               "value": 301
                           },
                           "status": "create",
                           "type": "primary"
                       }
                   ],
                   "wipe": false
               }
           ]
       },
       "disk_encryption": {
           "encryption_type": "luks",
           "partitions": [
               "3e75d045-21a4-429d-897e-8ec19a006e8b"
           ]
       },
       "hostname": "archlinux",
       "kernels": [
           "linux"
       ],
       "locale_config": {
           "kb_layout": "us",
           "sys_enc": "UTF-8",
           "sys_lang": "en_US"
       },
       "mirror_config": {
           "custom_mirrors": [],
           "mirror_regions": {
               "Sweden": [
                   "https://mirror.osbeck.com/archlinux/$repo/os/$arch",
                   "https://mirror.bahnhof.net/pub/archlinux/$repo/os/$arch",
                   "https://ftp.myrveln.se/pub/linux/archlinux/$repo/os/$arch",
                   "https://ftp.lysator.liu.se/pub/archlinux/$repo/os/$arch",
                   "https://ftp.ludd.ltu.se/mirrors/archlinux/$repo/os/$arch",
                   "https://ftp.acc.umu.se/mirror/archlinux/$repo/os/$arch",
                   "http://mirror.bahnhof.net/pub/archlinux/$repo/os/$arch",
                   "http://ftpmirror.infania.net/mirror/archlinux/$repo/os/$arch",
                   "http://ftp.myrveln.se/pub/linux/archlinux/$repo/os/$arch",
                   "http://ftp.lysator.liu.se/pub/archlinux/$repo/os/$arch",
                   "http://ftp.acc.umu.se/mirror/archlinux/$repo/os/$arch"
               ]
           }
       },
       "network_config": {},
       "no_pkg_lookups": false,
       "ntp": true,
       "offline": false,
       "packages": [],
       "parallel downloads": 0,
       "profile_config": null,
       "save_config": null,
       "script": "guided",
       "silent": false,
       "swap": true,
       "timezone": "UTC",
       "version": "2.6.0"
   }

``--config`` options
^^^^^^^^^^^^^^^^^^^^

*(Scroll to the right in the table to see required options.)*

.. csv-table:: JSON options
   :file: config_options.csv
   :widths: 15, 40, 40, 5
   :escape: !
   :header-rows: 1

.. note::

   If no entries are found in ``disk_config``, archinstall guided installation will use whatever is mounted currently under ``/mnt/archinstall`` without performing any disk operations.

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
