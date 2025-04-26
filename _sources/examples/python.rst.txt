.. _examples.python:

Python module
=============

Archinstall supports running in `module mode <https://docs.python.org/3/library/__main__.html>`_.
The way the library is invoked in module mode is limited to executing scripts under the `scripts`_ folder.

It's therefore important to place any script or profile you wish to invoke in the examples folder prior to building and installing.

Pre-requisites
--------------

We'll assume you've followed the :ref:`installing.python.manual` method.
Before actually installing the library, you will need to place your custom installer-scripts under `scripts`_ as a python file.

More on how you create these in the next section.

.. warning::

    This is subject to change in the future as this method is currently a bit stiff. The script path will become a parameter. But for now, this is by design.

Creating a script
-----------------

Lets create a `test_installer` - installer as an example. This is assuming that the folder `./archinstall` is a git-clone of the main repo.
We begin by creating "`scripts`_:code:`/test_installer.py`". The placement here is important later.

This script can now already be called using :code:`python -m archinstall test_installer` after a successful installation of the library itself.
But the script won't do much. So we'll do something simple like list all the hard drives as an example.

To do this, we'll begin by importing :code:`archinstall` in our "`scripts`_:code:`/test_installer.py`" and call a function whtin ``archinstall``.

.. code-block:: python

    import archinstall

    print(archinstall.disk.device_handler.devices)

Now, go ahead and reference the :ref:`installing.python.manual` installation method.
After running ``python -m archinstall test_installer`` it should print something that looks like:

.. code-block:: text

   [
       BDevice(
           disk=<parted.disk.Disk object at 0x7fbe17156050>,
           device_info=_DeviceInfo(
               model='PC801 NVMe SK hynix 512GB',
               path=PosixPath('/dev/nvme0n1'),
               type='nvme',
               total_size=Size(value=512110190592, unit=<Unit.B: 1>,
               sector_size=SectorSize(value=512, unit=<Unit.B: 1>)),
               free_space_regions=[
                   <archinstall.lib.disk.device_model.DeviceGeometry object at 0x7fbe166c4250>,
                   <archinstall.lib.disk.device_model.DeviceGeometry object at 0x7fbe166c4c50>,
                   <archinstall.lib.disk.device_model.DeviceGeometry object at 0x7fbe166c4a10>],
               sector_size=SectorSize(value=512, unit=<Unit.B: 1>),
               read_only=False,
               dirty=False
           ),
           partition_infos=[
               _PartitionInfo(
                   partition=<parted.partition.Partition object at 0x7fbe166c4a90>,
                   name='primary',
                   type=<PartitionType.Primary: 'primary'>,
                   fs_type=<FilesystemType.Fat32: 'fat32'>,
                   path='/dev/nvme0n1p1',
                   start=Size(value=2048, unit=<Unit.sectors: 'sectors'>, sector_size=SectorSize(value=512, unit=<Unit.B: 1>)),
                   length=Size(value=535822336, unit=<Unit.B: 1>, sector_size=SectorSize(value=512, unit=<Unit.B: 1>)),
                   flags=[
                       <PartitionFlag.BOOT: flag_id=1, alias=None>,
                       <PartitionFlag.ESP: flag_id=18, alias=None>
                   ],
                   partn=1,
                   partuuid='a26be943-c193-41f4-9930-9341cf5f6b19',
                   uuid='6EE9-2C00',
                   disk=<parted.disk.Disk object at 0x7fbe17156050>,
                   mountpoints=[
                       PosixPath('/boot')
                   ],
                   btrfs_subvol_infos=[]
               ),
               _PartitionInfo(...)
           ]
       )
   ]

That means your script is in the right place, and ``archinstall`` is working as intended.

.. note::

   Most calls, including the one above requires `root <https://en.wikipedia.org/wiki/Superuser>`_ privileges.


.. _scripts: https://github.com/archlinux/archinstall/tree/master/archinstall/scripts
