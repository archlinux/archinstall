.. _disk config:

Disk Configuration
==================

There are only three modes in the ``disk_config`` option. They are described in more detail below.

"Leave as is"
--------------

.. code-block:: json

   {
       "config_type": "pre_mounted_config",
       "mountpoint": "/mnt/archinstall"
   }

This mode will not perform any partitioning what so ever.
Instead it relies on what's mounted manually by the user under ``/mnt/archinstall``.

Given the following disk example:

.. code-block::

   /mnt/archinstall    (/dev/sda2)
        ├── boot       (/dev/sda1)
        └── home       (/dev/sda3)

Running ``archinstall --conf your.json --silent`` where the above JSON is configured. The disk will be left alone — and a working system will be installed to the above folders and mountpoints will be translated into the installed system.

.. note::

   Some disk layouts can be too complicated to detect, such as RAID setups. Please do report those setups on the `Issue Tracker <https://github.com/archlinux/archinstall>`__ so we can support them.

Best Effort
-----------

.. warning::

   This mode will wipe data!

.. note::

   Note that this options is similar to the manual partitioning but is generated through the menu system! And the best effort layout might deviate slightly from some wiki guidelines in order to facilitate some optional configurations at a later stage.

.. code-block:: json

   {
       "disk_config": {
           "config_type": "default_layout",
           "device_modifications": [
               {
                   "device": "/dev/sda",
                   "wipe": true,
                   "partitions": "..."
               }
           ]
       }
   }

This mode will attempt to configure a sane default layout on the selected disks.
Based on the chosen filesystem, and potential optional settings for said filesystem — different default layouts will be provided.

Manual Partitioning
-------------------

.. code-block:: json

   {
        "disk_config": {
            "config_type": "manual_partitioning",
            "device_modifications": [
               "filesystem struct"
            ]
        }
    }

Manual partitioning is the most complex one of the three. It offers you near endless flexibility of how to partition your disk. It integrates against `pyparted <https://github.com/dcantrell/pyparted>`__ and some control logic in ``archinstall`` that deals with creating things like subvolumes and compression.

Sizes are by default ``sector`` units, but other units are supported.

The options supplied to ``manual_partitioning`` are dictionary definitions, where the following parameters must exist:

.. csv-table:: JSON options
   :file: ./manual_options.csv
   :widths: 15, 15, 65, 5
   :escape: !
   :header-rows: 1

Each partition definition heavily relies on what filesystem is used.
Below follow two of the more common filesystems, anything else will best be described by running ``archinstall`` to generate a desired configuration for the desired filesystem type — and copy the relevant parts for permanent configurations.

.. warning::

   Important to note that the units and positions in the examples below — are highly user specific!

FAT32
^^^^^

.. code-block:: json

	{
		"btrfs": [],
		"flags": [
		   "boot"
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
	}

.. note::

   The ``Boot`` flag will make ``archinstall`` automatically set the correct ESP partition GUID if the system is booted with ``EFI`` support. The GUID will then be set to ``C12A7328-F81F-11D2-BA4B-00A0C93EC93B``.

EXT4
^^^^

.. code-block:: json

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

BTRFS
^^^^^

The BTRFS filesystem is inherently more complicated, thus the options are a bit more involved.
This example contains both subvolumes and compression.

.. note::

   Note that the ``"mountpoint": null`` is used for the overall partition, and instead individual subvolumes have mountpoints set.

.. code-block:: json

   {
      "btrfs": [
          {
              "mountpoint": "/",
              "name": "@",
          },
          {
              "mountpoint": "/home",
              "name": "@home",
          },
          {
              "mountpoint": "/var/log",
              "name": "@log",
          },
          {
              "mountpoint": "/var/cache/pacman/pkg",
              "name": "@pkg",
          },
          {
              "mountpoint": "/.snapshots",
              "name": "@.snapshots",
          }
      ],
      "dev_path": null,
      "flags": [],
      "fs_type": "btrfs",
      "mount_options": [
          "compress=zstd"
      ],
      "mountpoint": null,
      "obj_id": "d712357f-97cc-40f8-a095-24ff244d4539",
      "size": {
          "sector_size": {
              "unit": "B",
              "value": 512
          },
          "unit": "B",
          "value": 15568207872
      },
      "start": {
          "sector_size": {
              "unit": "B",
              "value": 512
          },
          "unit": "MiB",
          "value": 513
      },
      "status": "create",
      "type": "primary"
   }
