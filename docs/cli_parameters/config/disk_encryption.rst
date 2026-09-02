.. _disk encryption:

Disk Encryption
===============

Disk encryption consists of a top level entry in the user configuration.

.. code-block:: json

   {
        "disk_encryption": {
            "encryption_type": "luks",
            "partitions": [
                "d712357f-97cc-40f8-a095-24ff244d4539"
            ],
            "allow_discards": false
        }
   }

The ``UID`` in the ``partitions`` list is an internal reference to the ``obj_id`` in the :ref:`disk config` entries.

``allow_discards`` passes TRIM requests through to the underlying device, which is what lets an SSD reclaim blocks the filesystem has freed. The flag is written into the LUKS2 header when the device is created, so it applies to every later unlock without any extra kernel parameter.

It is off by default: on an encrypted device the pattern of used and unused blocks becomes visible to anyone who can read the disk, which can give away the filesystem type and how full it is.
