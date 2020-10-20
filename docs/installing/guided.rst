.. _installing.guided:

Guided installation
===================

This is the installer you'll encounter on the *(currently)* unofficial Arch Linux Archinstall ISO found on `archlinux.life <https://archlinux.life>`_.

You'll obviously need a physical machine or a virtual machine and have a basic understanding of how ISO-files work, where and how to mount them in order to boot the installer.

It runs you through a set of questions in order to determine what the system should look like. Then the guided installer performs the required installation steps for you. Some additional steps might show up depending on your chosen input at some of the steps - those steps should be self explanatory and won't be covered here.

.. note::
    There are some limitations with the installer, such as that it will not configure WiFi during the installation procedure. And it will not perform a post-installation network configuration either. So you need to read up on `Arch Linux networking <https://wiki.archlinux.org/index.php/Network_configuration>`_ to get that to work.

Features
--------

The guided installer currently supports:

 * *(optional)* Setting up disk encryption
 * *(optional)* Installing some simple desktop environments
 * Choosing between a super-user or root based user setup

Installation steps
------------------

The steps are ever so changing between versions.
But currently the steps are *(in order and explained briefly)*

Locale
^^^^^^

Asks what locale you want. This configures your keyboard layout both during the installation and mostly in the installed system as well.

Mirrors
^^^^^^^

Next step is to select where you want to download packages from.
Selecting a mirror-region will greatly increase speeds of the installation.

.. note::
    The step is **optional**, and Arch Linux have built-in tools to attempt to improve the mirror-order during the installation. It does behave slightly unpredictable in some regions, so selecting it manually is recommended for this installer.

Harddrive
^^^^^^^^^

The next step is to choose which medium to install to.
There are some limitations on what mediums the installer can detect and install on.
But for the most part, the following are supported:

 * IDE and SATA drives
 * NVMe and similar devices
 * loopback devices

Disk encryption
^^^^^^^^^^^^^^^

Selecting a disk encryption password enables disk encryption for the installation.

.. note::
    This step is highly recommended for most users, skipping this step comes with some risk so read up on why you would want to skip this before deciding to opt-out.

.. warning::
    This step does require at least 1GB of free RAM during boot in order to boot at all. Keep this in mind when creating virtual machines.

Hostname
^^^^^^^^

The hostname in which the machine will identify itself on the local network.
This step is optional, but a default hostname of `Archinstall` will be set if none is selected.

Root password
^^^^^^^^^^^^^

.. note::
    This step is optional and **it's recommended to skip** this step.

This gives you the option to re-enable the `root` account on the machine. By default, the `root` account on Arch Linux is disabled and does not contain a password.

Instead, you're recommended in the next step to set up a super-user.

Super-user
^^^^^^^^^^

.. note::
    This step only applies if you correctly skipped the previous step :ref:`root_password`_ which makes this step mandatory.

If the previous step was skipped, and only if it is skipped.
This step enables you to create a `sudo` enabled user with a password.

The sudo permission grants `root`-like privileges to the account but is less prone to guessing attacks and other security enhancing measures. You are also less likely to mess up system critical things by operating in normal user-mode and calling `sudo` to gain temporary administrative privileges.

Pre-programmed profiles
^^^^^^^^^^^^^^^^^^^^^^^

You can optionally choose to install a pre-programmed profile. These profiles might make it easier for new users or beginners to achieve a desktop environment as an example.

There is a list of profiles to choose from. If you are unsure of what any of these are, research the names that show up to understand what they are before you choose one.

Additional packages
^^^^^^^^^^^^^^^^^^^

Some additional packages can be installed if need be. This step allows you to list *(space separated)* officially supported packages from the `package database <https://www.archlinux.org/packages/>`_.

.. warning::
    When selecting *(or skipping)* this step. The installation will begin and your selected hard drive will be wiped after a 5 second countdown.

Post installation
-----------------

Once the installation is complete, green text should appear saying that it's safe to `reboot`, which is also the command you use to reboot.