.. _help.issues:

Issue tracker
=============

Issues should be reported over at `GitHub/issues <https://github.com/Torxed/archinstall/issues>`_.

General questions, enhancements and security issues can be reported over there too.
For quick issues or if you need help, head over the to the Discord server which has a help channel.

Submitting a help ticket
========================

When submitting a help ticket, please include the *install-session_\*.log* found under *~/.cache/archinstall/* on the installation medium.

.. code::bash

    cd ~/.cache/archinstall
    .
    ├── install-session_2020-11-08_10-43-50.665316.log
    └── workers
        ├── 1edc2abd08261603fb78a1f6083dc74654ea6625d167744221f6bd3dec4bcd5b
        ├── a7c8c2ceea27df2b483c493995556c86bc3e4a1befd0f6709ef6a56ff91d23f4
        └── fadaf96c1164684cc16b374f703f7d3b959545e1ec1fb5471ace9835bf105752

| You can submit the *install-session_2020-11-08_10-43-50.665316.log* in this example to the support personel.
| They might ask you for individual worker files as well, they contain the raw output from the individual commands executed such *pacman -S ...* etc.

.. warning::

    Worker log-files *may* contain sensitive information such as **passwords** and **private information**. Never submit these logs without going through them manually making sure they're good for submission. Or submit parts of it that's relevant to the issue itself.
