.. _installing.binary:

Binary executable
=================

Archinstall can be compiled into a standalone executable.
For Arch Linux based systems, there's a package for this called `archinstall <https://archlinux.org/packages/extra/any/archinstall/>`_.

.. warning::
    This is not required if you're running archinstall on a pre-built ISO. The installation is only required if you're creating your own scripted installations.

Using pacman
------------

Archinstall is on the `official repositories <https://wiki.archlinux.org/index.php/Official_repositories>`_.

.. code-block:: console

    sudo pacman -S archinstall

Using PKGBUILD
--------------

The `source <https://github.com/archlinux/archinstall>`_ contains a binary `PKGBUILD <https://github.com/Torxed/archinstall/tree/master/PKGBUILD/archinstall>`_ which can be either copied straight off the website. Or cloned using `git clone https://github.com/Torxed/archinstall`.

Once you've obtained the `PKGBUILD`, building it is pretty straight forward.

.. code-block:: console

    makepkg -s

Which should produce a `archinstall-X.x.z-1.pkg.tar.zst` that can be installed using:

.. code-block:: console

    sudo pacman -U archinstall-X.x.z-1.pkg.tar.zst

.. note::

    For a complete guide on the build process, please consult the `PKGBUILD on ArchWiki <https://wiki.archlinux.org/index.php/PKGBUILD>`_.

Manual compilation
------------------

You can compile the source manually without using a custom mirror or the `PKGBUILD` that is shipped.
Simply clone or download the source, and while standing in the cloned folder `./archinstall`, execute:

.. code-block:: console

    nuitka3  --standalone --show-progress archinstall

This requires the `nuitka <https://archlinux.org/packages/community/any/nuitka/>`_ package as well as `python3` to be installed locally.
