.. _help.known_issues:

Known Issues
============

Some issues are out of the `archinstall`_ projects scope, and the ones we know of are listed below.

.. _waiting for time sync:

Waiting for time sync `#2144`_
------------------------------

The usual root cause of this is the network topology.
More specifically `timedatectl show`_ cannot perform a proper time sync against the default servers.

Restarting ``systemd-timesyncd.service`` might work but most often you need to configure ``/etc/systemd/timesyncd.conf`` to match your network design.

.. note::

   If you know your time is correct on the machine, you can run ``archinstall --skip-ntp`` to ignore time sync.

Missing Nvidia Proprietary Driver `#2002`_
------------------------------------------

In some instances, the nvidia driver might not have all the necessary packages installed.
This is due to the kernel selection and/or hardware setups requiring additional packages to work properly.

A common workaround is to install the package `linux-headers`_ and `nvidia-dkms`_

ARM, 32bit and other CPU types error out `#1686`_, `#2185`_
-----------------------------------------------------------

This is a bit of a catch-all known issue.
Officially `x86_64`_ is only supported by Arch Linux.
Hence little effort have been put into supporting other platforms.

In theory, other architectures should work but small quirks might arise.

PR's are welcome but please be respectful of the delays in merging.
Other fixes, issues or features will be prioritized for the above reasons.

Keyring is out of date `#2213`_
-------------------------------

Missing key-issues tend to be that the `archlinux-keyring`_ package is out of date, usually as a result of an outdated ISO.
There is an attempt from upstream to fix this issue, and it's the `archlinux-keyring-wkd-sync.service`_

The service starts almost immediately during boot, and if network is not configured in time — the service will fail.
Subsequently the ``archinstall`` run might operate on a old keyring despite there being an update service for this.

There is really no way to reliably over time work around this issue in ``archinstall``.
Instead, efforts to the upstream service should be considered the way forward. And/or keys not expiring between a sane amount of ISO's.

.. note::

   The issue can happen on new ISO's too even as little as a few days after release, as some keys might expire right after the keyring is *"burnt in"* to the ISO.

.. note::

   Another common issue relating to the network not being configured, is that time might not be set correctly - resulting in the keyring not being able to update. See :ref:`waiting for time sync`.

AUR packages
------------

This is also a catch-all issue.
`AUR is unsupported <https://wiki.archlinux.org/title/Arch_User_Repository#Updating_packages>`_, and until that changes we cannot use AUR packages to solve feature requests in ``archinstall``.

This means that feature requests like supporting filesystems such as `ZFS`_ can not be added, and issues cannot be solved by using AUR packages either.

.. note::

   But in spirit of giving the community options, ``archinstall`` supports :ref:`archinstall.Plugins`, which means you can run ``archinstall --plugin <url>`` and source an AUR plugin.

   `torxed/archinstall-aur <https://github.com/torxed/archinstall-aur>`_ is a reference implementation for plugins:

   .. code-block:: console

      # archinstall --plugin https://archlinux.life/aur-plugin

   `phisch/archinstall-aur <https://github.com/phisch/archinstall-aur>`_ is another alternative:

   .. code-block:: console

      # archinstall --plugin https://raw.githubusercontent.com/phisch/archinstall-aur/master/archinstall-aur.py

   .. warning::

      This will allow for unsupported usage of AUR during installation.

.. _#2213: https://github.com/archlinux/archinstall/issues/2213
.. _#2185: https://github.com/archlinux/archinstall/issues/2185
.. _#2144: https://github.com/archlinux/archinstall/issues/2144
.. _#2002: https://github.com/archlinux/archinstall/issues/2002
.. _#1686: https://github.com/archlinux/archinstall/issues/1686
.. _linux-headers: https://archlinux.org/packages/core/x86_64/linux-headers/
.. _nvidia-dkms: https://archlinux.org/packages/extra/x86_64/nvidia-dkms/
.. _x86_64: https://wiki.archlinux.org/title/Frequently_asked_questions#What_architectures_does_Arch_support?
.. _archlinux-keyring: https://archlinux.org/packages/core/any/archlinux-keyring/
.. _archlinux-keyring-wkd-sync.service: https://gitlab.archlinux.org/archlinux/archlinux-keyring/-/blob/7e672dad10652a80d1cc575d75cdb46442cd7f96/wkd_sync/archlinux-keyring-wkd-sync.service.in
.. _ZFS: https://aur.archlinux.org/packages/zfs-linux
.. _archinstall: https://github.com/archlinux/archinstall/
.. _timedatectl show: https://github.com/archlinux/archinstall/blob/e6344f93f7e476d05bbcd642f2ed91fdde545870/archinstall/lib/installer.py#L136
