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
            ]
        }
   }

The ``UID`` in the ``partitions`` list is an internal reference to the ``obj_id`` in the :ref:`disk config` entries.