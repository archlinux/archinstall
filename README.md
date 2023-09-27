<!-- <div align="center"> -->
<img src="https://github.com/archlinux/archinstall/raw/master/docs/logo.png" alt="drawing" width="200"/>

<!-- </div> -->
# Arch Installer
[![Lint Python and Find Syntax Errors](https://github.com/archlinux/archinstall/actions/workflows/flake8.yaml/badge.svg)](https://github.com/archlinux/archinstall/actions/workflows/flake8.yaml)

Just another guided/automated [Arch Linux](https://wiki.archlinux.org/index.php/Arch_Linux) installer with a twist.
The installer also doubles as a python library to install Arch Linux and manage services, packages and other things inside the installed system *(Usually from a live medium)*.

* archinstall [discord](https://discord.gg/cqXU88y) server
* archinstall [matrix.org](https://app.element.io/#/room/#archinstall:matrix.org) channel
* archinstall [#archinstall@irc.libera.chat](irc://#archinstall@irc.libera.chat:6697)
* archinstall [documentation](https://archinstall.readthedocs.io/)

# Installation & Usage

    $ sudo pacman -S archinstall

Alternative ways to install are `git clone` the repository or `pip install --upgrade archinstall`.

## Running the [guided](https://github.com/archlinux/archinstall/blob/master/archinstall/scripts/guided.py) installer

Assuming you are on an Arch Linux live-ISO or installed via `pip`:

    # archinstall

## Running the [guided](https://github.com/archlinux/archinstall/blob/master/archinstall/scripts/guided.py) installer using `git`

    # cd archinstall-git
    # cp archinstall/scripts/guided.py
    # python guided.py

#### Advanced
Some additional options that are not needed by most users are hidden behind the `--advanced` flag.

## Running from a declarative configuration file or URL

`archinstall` can be run with a JSON configuration file. There are 2 different configuration files to consider,
the `user_configuration.json` contains all general installation configuration, whereas the `user_credentials.json`
contains the sensitive user configuration such as user password, root password and encryption password.

An example of the user configuration file can be found here
[configuration file](https://github.com/archlinux/archinstall/blob/master/examples/config-sample.json)
and example of the credentials configuration here
[credentials file](https://github.com/archlinux/archinstall/blob/master/examples/creds-sample.json).

**HINT:** The configuration files can be auto-generated by starting `archinstall`, configuring all desired menu
points and then going to `Save configuration`.

To load the configuration file into `archinstall` run the following command
```
archinstall --config <path to user config file or URL> --creds <path to user credentials config file or URL>
```

# Help or Issues

If any issues are encountered please submit an issue here on Github or submit a post in the discord help channel.
When submitting an issue, please:
* Provide the stacktrace of the output if there is any
* Attach the `/var/log/archinstall/install.log` to the issue ticket. This helps us help you!
  * To extract the log from the ISO image, one way is to use<br>
    ```curl -F'file=@/var/log/archinstall/install.log' https://0x0.st```


# Available Languages

Archinstall is available in different languages which have been contributed and are maintained by the community.
The language can be switched inside the installer (first menu entry). Bare in mind that not all languages provide
full translations as we rely on contributors to do the translations. Each language has an indicator that shows
how much has been translated.

Any contributions to the translations are more than welcome,
to get started please follow [the guide](https://github.com/archlinux/archinstall/blob/master/archinstall/locales/README.md)

## Fonts
The ISO does not ship with ship with all fonts needed for different languages.
Fonts that are using a different character set than Latin will not be displayed correctly. If those languages
want to be selected than a proper font has to be set manually in the console.

All available console fonts can be found in `/usr/share/kbd/consolefonts` and can be set with `setfont LatGrkCyr-8x16`.


# Scripting your own installation

## Scripting interactive installation

There are some examples in the `examples/` directory that should serve as a starting point.

The following is a small example of how to script your own *interactive* installation:

```python
from pathlib import Path

from archinstall import Installer, ProfileConfiguration, profile_handler, User
from archinstall.default_profiles.minimal import MinimalProfile
from archinstall.lib.disk.device_model import FilesystemType
from archinstall.lib.disk.encryption_menu import DiskEncryptionMenu
from archinstall.lib.disk.filesystem import FilesystemHandler
from archinstall.lib.interactions.disk_conf import select_disk_config

fs_type = FilesystemType('ext4')

# Select a device to use for the installation
disk_config = select_disk_config()

# Optional: ask for disk encryption configuration
data_store = {}
disk_encryption = DiskEncryptionMenu(disk_config.device_modifications, data_store).run()

# initiate file handler with the disk config and the optional disk encryption config
fs_handler = FilesystemHandler(disk_config, disk_encryption)

# perform all file operations
# WARNING: this will potentially format the filesystem and delete all data
fs_handler.perform_filesystem_operations()

mountpoint = Path('/tmp')

with Installer(
        mountpoint,
        disk_config,
        disk_encryption=disk_encryption,
        kernels=['linux']
) as installation:
    installation.mount_ordered_layout()
    installation.minimal_installation(hostname='minimal-arch')
    installation.add_additional_packages(['nano', 'wget', 'git'])

    # Optionally, install a profile of choice.
    # In this case, we install a minimal profile that is empty
    profile_config = ProfileConfiguration(MinimalProfile())
    profile_handler.install_profile_config(installation, profile_config)

    user = User('archinstall', 'password', True)
    installation.create_users(user)
```

This installer will perform the following:

* Prompt the user to configurate the disk partitioning
* Prompt the user to setup disk encryption
* Create a file handler instance for the configured disk and the optional disk encryption
* Perform the disk operations (WARNING: this will potentially format the disks and erase all data)
* Installs a basic instance of Arch Linux *(base base-devel linux linux-firmware btrfs-progs efibootmgr)*
* Installs and configures a bootloader to partition 0 on uefi. On BIOS, it sets the root to partition 0.
* Install additional packages *(nano, wget, git)*
* Create a new user

> **Creating your own ISO with this script on it:** Follow [ArchISO](https://wiki.archlinux.org/index.php/archiso)'s guide on how to create your own ISO.

## Script non-interactive automated installation

For an example of a fully scripted, automated installation please see the example
[full_automated_installation.py](https://github.com/archlinux/archinstall/blob/master/examples/full_automated_installation.py)

## Unattended installation based on MAC address

Archinstall comes with an [unattended](https://github.com/archlinux/archinstall/blob/master/examples/mac_address_installation.py)
example which will look for a matching profile for the machine it is being run on, based on any local MAC address.
For instance, if the machine the code is executed on has the MAC address `52:54:00:12:34:56` it will look for a profile called
[52-54-00-12-34-56.py](https://github.com/archlinux/archinstall/blob/master/archinstall/default_profiles/tailored.py).
If it's found, the unattended installation will commence and source that profile as its installation procedure.

# Profiles

`archinstall` ships with a set of pre-defined profiles that can be chosen during the installation process.

- [Desktop](https://github.com/archlinux/archinstall/tree/master/archinstall/default_profiles/desktops)
- [Server](https://github.com/archlinux/archinstall/tree/master/archinstall/default_profiles/servers)

The definitions of the profiles and what packages they will install can be seen directly in the menu or
[default profiles](https://github.com/archlinux/archinstall/tree/master/archinstall/default_profiles)


# Testing

## Using a Live ISO Image

If you want to test a commit, branch or bleeding edge release from the repository using the vanilla Arch Live ISO image,
you can replace the version of archinstall with a new version and run that with the steps described below.

*Note: When booting from a live USB then the space on the ramdisk is limited and may not be sufficient to allow
running a re-installation or upgrade of the installer. In case one runs into this issue, any of the following can be used
- Resize the root partition on the fly https://wiki.archlinux.org/title/Archiso#Adjusting_the_size_of_root_partition_on_the_fly
- The boot parameter `copytoram=y` (https://gitlab.archlinux.org/archlinux/mkinitcpio/mkinitcpio-archiso/-/blob/master/docs/README.bootparams#L26)
can be specified which will copy the root filesystem to tmpfs.*

1. You need a working network connection
2. Install the build requirements with `pacman -Sy; pacman -S git python-pip gcc pkgconf`
   *(note that this may or may not work depending on your RAM and current state of the squashfs maximum filesystem free space)*
3. Uninstall the previous version of archinstall with `pip uninstall --break-system-packages archinstall`
4. Now clone the latest repository with `git clone https://github.com/archlinux/archinstall`
5. Enter the repository with `cd archinstall`
   *At this stage, you can choose to check out a feature branch for instance with `git checkout v2.3.1-rc1`*
6. To run the source code, there are 2 different options:
   - Run a specific branch version from source directly using `python -m archinstall`, in most cases this will work just fine, the
      rare case it will not work is if the source has introduced any new dependencies that are not installed yet
   - Installing the branch version with `pip install --break-system-packages .` and `archinstall`

## Without a Live ISO Image

To test this without a live ISO, the simplest approach is to use a local image and create a loop device.<br>
This can be done by installing `pacman -S arch-install-scripts util-linux` locally and doing the following:

    # truncate -s 20G testimage.img
    # losetup -fP ./testimage.img
    # losetup -a | grep "testimage.img" | awk -F ":" '{print $1}'
    # pip install --upgrade archinstall
    # python -m archinstall --script guided
    # qemu-system-x86_64 -enable-kvm -machine q35,accel=kvm -device intel-iommu -cpu host -m 4096 -boot order=d -drive file=./testimage.img,format=raw -drive if=pflash,format=raw,readonly,file=/usr/share/ovmf/x64/OVMF_CODE.fd -drive if=pflash,format=raw,readonly,file=/usr/share/ovmf/x64/OVMF_VARS.fd

This will create a *20 GB* `testimage.img` and create a loop device which we can use to format and install to.<br>
`archinstall` is installed and executed in [guided mode](#docs-todo). Once the installation is complete, ~~you can use qemu/kvm to boot the test media.~~<br>
*(You'd actually need to do some EFI magic in order to point the EFI vars to the partition 0 in the test medium, so this won't work entirely out of the box, but that gives you a general idea of what we're going for here)*

There's also a [Building and Testing](https://github.com/archlinux/archinstall/wiki/Building-and-Testing) guide.<br>
It will go through everything from packaging, building and running *(with qemu)* the installer against a dev branch.


# FAQ

## How to dual boot with Windows

`archinstall` can be used to install Arch alongside an existing Windows installation.
Below are the necessary steps:
* After the Windows installation make sure there is some unallocated space for a Linux installation available
* Boot into the ISO and run`archinstall`
* Select `Disk configuration` -> `Manual partitioning`
* Select the disk on which Windows resides
* Chose `Create a new partition`
* Select a filesystem type
* Now the location of the new partition has to be specified as start and end sectors (values can be suffixed with various units)
* Assign mountpoint `/`
* Back in the partitioning menu, assign the `Boot/ESP` partition the mountpoint `/boot`
* This is all for the partitioning menu, select `Confirm and exit` to return to the main menu
* Set any additional settings you would like to have for the installation
* After completing the setup start the installation


# Mission Statement

Archinstall promises to ship a [guided installer](https://github.com/archlinux/archinstall/blob/master/archinstall/scripts/guided.py) that follows
the [Arch Principles](https://wiki.archlinux.org/index.php/Arch_Linux#Principles) as well as a library to manage services, packages and other Arch Linux aspects.

The guided installer will provide user-friendly options along the way, but the keyword here is options, they are optional and will never be forced upon anyone.
The guided installer itself is also optional to use if so desired and not forced upon anyone.

---

Archinstall has one fundamental function which is to be a flexible library to manage services, packages and other aspects inside the installed system.
This library is in turn used by the provided guided installer but is also for anyone who wants to script their own installations.

Therefore, Archinstall will try its best to not introduce any breaking changes except for major releases which may break backwards compatibility after notifying about such changes.


# Contributing

Please see [CONTRIBUTING.md](https://github.com/archlinux/archinstall/blob/master/CONTRIBUTING.md)
