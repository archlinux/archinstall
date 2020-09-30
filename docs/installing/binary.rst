.. _installing.binary

Binary executable
=================

Archinstall can be compiled into a standalone executable.
For Arch Linux based systems, there's a package for this called `archinstall <https://archlinux.life/>`_.

.. warning::
    This is not required if you're running archinstall on a pre-built ISO. The installation is only required if you're creating your own scripted installations.

Using pacman
------------

Currently, you need to create your own mirror or use https://archlinux.life as a mirror.
We'll use the later for this example as it's less of a process to explain.

..note:: To create your own mirror, the `archiso <https://wiki.archlinux.org/index.php/archiso#Custom_local_repository>`_ wiki has a good tutorial and explanation of how and what a custom mirror does.

Setup pacman to use https://archlinux.life as a mirror by modifying `/etc/pacman.conf` to contain the following:

.. code-block:: console

    [archlife]
    Server = https://archlinux.life/$repo/os/$arch
    SigLevel = Optional TrustAll

You can now update your mirror-list and install `archinstall`.

.. code-block:: console

    sudo pacman -Syy
    sudo pacman -S archinstall

Using PKGBUILD
--------------

The `source <https://github.com/Torxed/archinstall>`_ contains a binary `PKGBUILD <https://github.com/Torxed/archinstall/tree/master/PKGBUILD/archinstall>`_ which can be either copied straight off the website. Or cloned using `git clone https://github.com/Torxed/archinstall`.

Once you've obtained the `PKGBUILD`, building it is pretty straight forward.

.. code-block:: console

    makepkg -s

Which should produce a `archinstall-X.x.z-1.pkg.tar.zst` that can be installed using:

.. code-block:: console

    sudo pacman -U archinstall-X.x.z-1.pkg.tar.zst

.. note::

    For a complete guide on the build process, please consult the wiki on `PKGBUILD <https://wiki.archlinux.org/index.php/PKGBUILD>`_.

Manual compilation
------------------

You can compile the source manually without using a custom mirror or the `PKGBUILD` that is shipped.
Simply clone or download the source, and while standing in the cloned folder `./archinstall`, execute:

.. code-block:: console

    nuitka3  --standalone --show-progress archinstall

This requires the `nuitka <https://www.archlinux.org/packages/community/any/nuitka/>`_ package as well as `python3` to be installed locally.