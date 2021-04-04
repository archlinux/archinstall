.. _installing.python:

Python library
==============

Archinstall ships on `PyPi <https://pypi.org/>`_ as `archinstall <pypi.org/project/archinstall/>`_.
But the library can be installed manually as well.

.. warning::
    This is not required if you're running archinstall on a pre-built ISO. The installation is only required if you're creating your own scripted installations.

Using pacman
------------

Archinstall is on the `official repositories <https://wiki.archlinux.org/index.php/Official_repositories>`_.

To install both the library and the archinstall script:

.. code-block:: console

    sudo pacman -S archinstall

Or, to install just the library:

.. code-block:: console

    sudo pacman -S python-archinstall

Using PyPi
----------

The basic concept of PyPi applies using `pip`.
Either as a global library:

.. code-block:: console

    sudo pip install archinstall

Or as a user module:

.. code-block:: console

    pip --user install archinstall

Which will allow you to start using the library.

.. _installing.python.manual:

Manual installation
-------------------

You can either download the github repo as a zip archive.
Or you can clone it, we'll clone it here but both methods work the same.

.. code-block:: console

    git clone https://github.com/archlinux/archinstall

Either you can move the folder into your project and simply do

.. code-block:: python

    import archinstall

Or you can use `setuptools <https://pypi.org/project/setuptools/>`_ to install it into the module path.

.. code-block:: console

    sudo python setup.py install