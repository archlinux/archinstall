.. _custom commands:

Custom Commands
===============

| Custom commands is a configuration entry that allows for executing custom commands post-installation.
| The commands are executed with `arch-chroot <https://man.archlinux.org/man/extra/arch-install-scripts/arch-chroot.8.en>`_.

The option takes a list of arguments, an example is:

.. code-block:: json

   {
       "custom-commands": [
           "hostname new-hostname"
       ]
   }

| The following example will set a new hostname in the installed system.
| The example is just to illustrate that the command is not run in the ISO but inside the installed system after the base system is installed.

More examples can be found in the code repository under `examples/ <https://github.com/archlinux/archinstall/tree/e6344f93f7e476d05bbcd642f2ed91fdde545870/examples>`_