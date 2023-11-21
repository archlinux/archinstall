.. _help.issues:

Known Issues
============

Some issues are out of the `archinstall`_ projects scope, and the ones we know of are listed below.

Waiting for time sync `#2144`_
------------------------------

| The usual root cause of this is the network topology.
| More specifically `timedatectl show`_ cannot perform a proper time sync against the default servers.

| A *"fix"* for this is mentioned in the issue above.
| That is to configure ``/etc/systemd/timesyncd.conf`` and restart ``systemd-timesyncd.service``.

.. note::

   A proposal to override the time sync check has been put up for discussion in `#2144`_.

.. _#2144: https://github.com/archlinux/archinstall/issues/2144
.. _archinstall: https://github.com/archlinux/archinstall/
.. _timedatectl show: https://github.com/archlinux/archinstall/blob/e6344f93f7e476d05bbcd642f2ed91fdde545870/archinstall/lib/installer.py#L136