.. _help.issues:

Issue tracker & bugs
====================

Issues and bugs should be reported over at `https://github.com/archlinux/archinstall/issues <https://github.com/Torxed/archinstall/issues>`_.

General questions, enhancements and security issues can be reported over there too.
For quick issues or if you need help, head over to the Discord server which has a help channel.

Log files
---------

| When submitting a help ticket, please include the :code:`/var/log/archinstall/install.log`.
| It can be found both on the live ISO but also in the installed filesystem if the base packages were strapped in.

| There are additional log files under ``/var/log/archinstall/`` that can be useful.
| For instance the ``cmd_history.txt`` which contains a fully transparent list of all commands executed.
| Or ``cmd_output.txt`` which is a transcript and contains any output seen on the screen.

.. warning::

    We only try to guarantee that ``/var/log/archinstall/install.log`` is free from sensitive information.
    Any other log should be pasted with **utmost care**!
