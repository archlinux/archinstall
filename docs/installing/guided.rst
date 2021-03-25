Guided installation
===================

This is the default scripted installation you'll encounter on the official Arch Linux Archinstall package as well as the unofficial ISO found on `https://archlinux.life <https://archlinux.life>`_. It will guide your through a very basic installation of Arch Linux.

The installer has two pre-requisits:

 * A Physical or Virtual machine to install on
 * An active internet connection prior to running archinstall

.. warning::
    A basic understanding of how machines, ISO-files and command lines are needed.
    Please read the official Arch Linux Wiki *(`https://wiki.archlinux.org/ <https://wiki.archlinux.org/>`_ to learn more)*

.. note::
    There are some limitations with the installer, such as that it will not configure WiFi during the installation procedure. And it will not perform a post-installation network configuration either. So you need to read up on `Arch Linux networking <https://wiki.archlinux.org/index.php/Network_configuration>`_ to get that to work.

Running the guided installation
-------------------------------

.. note::
    Due to the package being quite new, it might be required to update the local package list before installing or continuing. Partial upgrades can cause issues, but the lack of dependencies should make this perfectly safe:

    .. code::bash
        # pacman -Syy

To install archinstall and subsequently the guided installer, simply do the following:

.. code::bash
    # pacman -S python-archinstall

And to run it, execute archinstall as a Python module:

.. code::bash
    # python -m archinstall guided

| The guided parameter is optional as it's the default behavior.
| But this will start the process of guiding you through a installation of a quite minimal Arch Linux experience.

Description individual steps
============================

Below is a description of each individual steps in order.

keyboard languages
------------------

Default is :code:`us`.

| A short list of the most common layouts are presented.
| Entering :code:`?` and pressing enter enables a search mode where additional keyboard layouts can be found.

In search mode, you'll find things like:

 * :code:`sv-latin1` for swedish layouts

Mirror region selection
-----------------------

Default is :code:`auto detect best mirror`

| Leaving this blank should enable the most appropriate mirror for you.
| But if you want to override and use only one selected region, you can enter one in this step.

As an example:

 * :code:`Sweden` *(with a capital :code:`S`)* will only use mirrors from Sweden.

Selection of drive
------------------

There is no default for this step and it's a required step.

.. warning::
    | The selected device will be wiped completely!
    | 
    | Make sure you select a drive that will be used only by Arch Linux.
    | *(Future versions of archinstall will support multiboot on the same drive and more complex partition setups)*

Select the appropriate drive by selecting it by number or full path.

Disk encryption
---------------

Selecting a disk encryption password enables disk encryption for the OS partition.

.. note::
    This step is highly recommended for most users, skipping this step comes with some risk and you are obligated to read up on why you would want to skip encryption before deciding to opt-out.

.. warning::
    This step does require at least 1GB of free RAM during boot in order to boot at all. Keep this in mind when creating virtual machines. It also only encrypts the OS partition - not the boot partition *(it's not full disk encryption)*.

Hostname
--------

Default is :code:`Archinstall`

The hostname in which the machine will identify itself on the local network.
This step is optional, but a default hostname of `Archinstall` will be set if none is selected.

.. _root_password:

Root password
-------------

.. warning::
    | Setting a root password disables sudo permissions for additional users.
    | It's there for **recommended to skip this step**!

This gives you the option to re-enable the :code:`root` account on the machine. By default, the :code:`root` account on Arch Linux is disabled and does not contain a password.

You are instead recommended to skip to the next step without any input.

Super User (sudo)
-----------------

.. warning::
    This step only applies if you correctly skipped :ref:`the previous step <root_password>` which also makes this step mandatory.

If the previous step was skipped, and only if it is skipped.
This step enables you to create a :code:`sudo` enabled user with a password.

.. note::
    The sudo permission grants :code:`root`-like privileges to the account but is less prone to for instance guessing admin account attacks. You are also less likely to mess up system critical things by operating in normal user-mode and calling `sudo` to gain temporary administrative privileges.

Pre-programmed profiles
-----------------------

You can optionally choose to install a pre-programmed profile. These profiles might make it easier for new users or beginners to achieve a traditional desktop environment as an example.

There is a list of profiles to choose from. If you are unsure of what any of these are, research the names that show up to understand what they are before you choose one.

.. note::
    | Some profiles might have sub-dependencies that will ask you to select additional profiles.
    | For instance the :code:`desktop` profile will create a secondary menu to select a graphical driver. That graphical driver might have additional dependencies if there are multiple driver vendors.
    | 
    | Simply follow the instructions on the screen to navigate through them.

Additional packages
-------------------

Some additional packages can be installed if need be. This step allows you to list *(space separated)* officially supported packages from the package database at `https://archlinux.org/packages/ <https://archlinux.org/packages/>`_.


Network configuration
---------------------

| In this step is optional and allows for some basic configuration of your network.
| There are two main options and two sub-options, the two main ones are:

 * Copy existing network configuration from the ISO you're working on
 * Select **one** network interface to configure

| If copying existing configuration is chosen, no further configuration is needed.
| The installer will copy any wireless *(based on :code:`iwd`)* configurations and :code:`systemd-networkd` configuration set up by the user or the default system configuration.

| If a interface was selected instead, a secondary option will be presented, allowing you to choose between two options:

 * Automatic DHCP configuration of IP, DNS and Gateway
 * Static IP configuration that further will ask some mandatory questions

Configuration verification
--------------------------

| Before the installer continues, and this is only valid for the **guided installation**.
| The chosen configuration will be printed on the screen and you have the option to verify it.

After which you can press :code:`Enter` can be pressed in order to start the formatting and installation process.

.. warning::
    After a 5 second countdown, the selected drive will be permanently erased and all data will be lost.

Post installation
-----------------

Once the installation is complete, green text should appear saying that it's safe to `reboot`, which is also the command you use to reboot.
