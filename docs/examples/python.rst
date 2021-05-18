.. _examples.python:

Python module
=============

Archinstall supports running in `module mode <https://docs.python.org/3/library/__main__.html>`_.
The way the library is invoked in module mode is limited to executing scripts under the **example** folder.

It's there for important to place any script or profile you wish to invoke in the examples folder prior to building and installing.

Pre-requisites
--------------

We'll assume you've followed the :ref:`installing.python.manual` method.
Before actually installing the library, you will need to place your custom installer-scripts under `./archinstall/examples/` as a python file.

More on how you create these in the next section.

.. warning::

    This is subject to change in the future as this method is currently a bit stiff. The script path will become a parameter. But for now, this is by design.

Creating a script
-----------------

Lets create a `test_installer` - installer as an example. This is assuming that the folder `./archinstall` is a git-clone of the main repo.
We begin by creating `./archinstall/examples/test_installer.py`. The placement here is important later.

This script can now already be called using `python -m archinstall test_installer` after a successful installation of the library itself.
But the script won't do much. So we'll do something simple like list all the hard drives as an example.

To do this, we'll begin by importing `archinstall` in our `./archinstall/examples/test_installer.py` and call some functions.

.. code-block:: python

    import archinstall
    
    all_drives = archinstall.list_drives()
    print(all_drives)

This should print out a list of drives and some meta-information about them.
As an example, this will do just fine.

Now, go ahead and install the library either as a user-module or system-wide.

Calling a module
----------------

Assuming you've followed the example in `Creating a script`_, you can now safely call it with:

.. code-block:: console

    python -m archinstall test_installer

This should now print all available drives on your system.

.. note::

    This should work on any system, not just Arch Linux based ones. But note that other functions in the library relies heavily on Arch Linux based commands to execute the installation steps. Such as `arch-chroot`.
