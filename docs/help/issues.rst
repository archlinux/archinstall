.. _help.issues:

Issue tracker & bugs
====================

Issues and bugs should be reported over at `https://github.com/archlinux/archinstall/issues <https://github.com/Torxed/archinstall/issues>`_.

General questions, enhancements and security issues can be reported over there too.
For quick issues or if you need help, head over the to the Discord server which has a help channel.

Submitting a help ticket
========================

| When submitting a help ticket, please include the :code:`/var/log/archinstall/install.log`.
| It can be found both on the live ISO but also in the installed filesystem if the base packages was strapped in.

| There are additional worker files, these worker files contain individual command input and output.
| These worker files are located in :code:`~/.cache/archinstall/` and does not need to be submitted by default when submitting issues.

.. warning::

    Worker log-files *may* contain sensitive information such as **passwords** and **private information**. Never submit these logs without going through them manually making sure they're good for submission. Or submit parts of it that's relevant to the issue itself.
