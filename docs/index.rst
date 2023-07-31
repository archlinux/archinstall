archinstall Documentation
=========================

| **archinstall** is library which can be used to install Arch Linux.
| The library comes packaged with different pre-configured installers, such as the default :ref:`guided` installer.
| 
| A demo of the :ref:`guided` installer can be seen here: `https://www.youtube.com/watch?v=9Xt7X_Iqg6E <https://www.youtube.com/watch?v=9Xt7X_Iqg6E>`_.

Some of the features of Archinstall are:

* **Context friendly.** The library always executes calls in sequential order to ensure installation-steps don't overlap or execute in the wrong order. It also supports *(and uses)* context wrappers to ensure cleanup and final tasks such as ``mkinitcpio`` are called when needed.

* **Full transparency** Logs and insights can be found at ``/var/log/archinstall`` both in the live ISO and the installed system.

* **Accessibility friendly** Archinstall works with ``espeakup`` and other accessibility tools thanks to the use of a TUI.

.. toctree::
   :maxdepth: 1
   :caption: Running Archinstall

   installing/guided

.. toctree::
   :maxdepth: 3
   :caption: Getting help

   help/discord
   help/issues

.. toctree::
   :maxdepth: 3
   :caption: Archinstall as a library

   installing/python
   examples/python

.. toctree::
   :maxdepth: 3
   :caption: API Reference

   archinstall/Installer
