.. _examples.binary:

Binary executable
=================

.. warning:: The binary option is limited and stiff. It's hard to modify or create your own installer-scripts this way unless you compile the source manually. If your usecase needs custom scripts, either use the pypi setup method or you'll need to adjust the PKGBUILD prior to building the arch package.

The binary executable is a standalone compiled version of the library.
It's compiled using `nuitka <https://nuitka.net/>`_ with the flag `--standalone`.

Executing the binary
--------------------

As an example we'll use the `guided <https://github.com/archlinux/archinstall/blob/master/examples/guided.py>`_ installer.
To run the `guided` installed, all you have to do *(after installing or compiling the binary)*, is run:


.. code-block:: console

    ./archinstall guided

As mentioned, the binary is a bit rudimentary and only supports executing whatever is found directly under `./archinstall/examples`.
Anything else won't be found. This is subject to change in the future to make it a bit more flexible.
