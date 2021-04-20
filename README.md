<!-- <div align="center"> -->
<img src="https://github.com/archlinux/archinstall/raw/master/docs/logo.png" alt="drawing" width="200"/>

# Arch Installer
<!-- </div> -->

Just another guided/automated [Arch Linux](https://wiki.archlinux.org/index.php/Arch_Linux) installer with a twist.
The installer also doubles as a python library to install Arch Linux and manage services, packages and other things inside the installed system *(Usually from a live medium)*.

 * archinstall [discord](https://discord.gg/cqXU88y) server
 * archinstall [matrix.org](https://app.element.io/#/room/#archinstall:matrix.org) channel
 * archinstall [#archinstall@freenode (IRC)](irc://#archinstall@FreeNode)
 * archinstall [documentation](https://python-archinstall.readthedocs.io/en/latest/index.html)


# Installation & Usage

    $ sudo pacman -S archinstall

Or simply `git clone` the repo as it has no external dependencies *(but there are optional ones)*.<br>
Or use `pip install --upgrade archinstall` to use as a library.

## Running the [guided](examples/guided.py) installer

Assuming you are on a Arch Linux live-ISO and booted into EFI mode.

    # python -m archinstall guided

# Mission Statement

Archinstall promises to ship a [guided installer](https://github.com/archlinux/archinstall/blob/master/examples/guided.py) that follows the [Arch Principles](https://wiki.archlinux.org/index.php/Arch_Linux#Principles) as well as a library to manage services, packages and other Arch Linux aspects.

The guided installer will provide user friendly options along the way, but the keyword here is options, they are optional and will never be forced upon anyone. The guided installer itself is also optional to use if so desired and not forced upon anyone.

---

Archinstall has one fundamental function which is to be a flexible library to manage services, packages and other aspects inside the installed system. This library is in turn used by the provided guided installer but is also for anyone who wants to script their own installations.

Therefore, Archinstall will try its best to not introduce any breaking changes except for major releases which may break backwards compability after notifying about such changes.

# Scripting your own installation

You could just copy [guided.py](examples/guided.py) as a starting point.

But assuming you're building your own ISO and want to create an automated install process, or you want to install virtual machines on to local disk images.<br>
This is probably what you'll need, a [minimal example](examples/minimal.py) of how to install using archinstall as a Python library.

```python
import archinstall, getpass

# Select a harddrive and a disk password
harddrive = archinstall.select_disk(archinstall.all_disks())
disk_password = getpass.getpass(prompt='Disk password (won\'t echo): ')

# We disable safety precautions in the library that protects the partitions
harddrive.keep_partitions = False

# First, we configure the basic filesystem layout
with archinstall.Filesystem(harddrive, archinstall.GPT) as fs:
    # We create a filesystem layout that will use the entire drive
    # (this is a helper function, you can partition manually as well)
    fs.use_entire_disk(root_filesystem_type='btrfs')

    boot = fs.find_partition('/boot')
    root = fs.find_partition('/')

    boot.format('vfat')

    # Set the flag for encrypted to allow for encryption and then encrypt
    root.encrypted = True
    root.encrypt(password=disk_password)

with archinstall.luks2(root, 'luksloop', disk_password) as unlocked_root:
    unlocked_root.format(root.filesystem)
    unlocked_root.mount('/mnt')

    boot.mount('/mnt/boot')

with archinstall.Installer('/mnt') as installation:
    if installation.minimal_installation():
        installation.set_hostname('minimal-arch')
        installation.add_bootloader()

        installation.add_additional_packages(['nano', 'wget', 'git'])

        # Optionally, install a profile of choice.
        # In this case, we install a minimal profile that is empty
        installation.install_profile('minimal')

        installation.user_create('devel', 'devel')
        installation.user_set_pw('root', 'airoot')
        
```

This installer will perform the following:

 * Prompt the user to select a disk and disk-password
 * Proceed to wipe the selected disk with a `GPT` partition table on a UEFI system and MBR on a bios system.
 * Sets up a default 100% used disk with encryption.
 * Installs a basic instance of Arch Linux *(base base-devel linux linux-firmware btrfs-progs efibootmgr)*
 * Installs and configures a bootloader to partition 0 on uefi. on bios it sets the root to partition 0.
 * Install additional packages *(nano, wget, git)*
 * Installs a profile with a window manager called [awesome](https://github.com/archlinux/archinstall/blob/master/profiles/awesome.py) *(more on profile installations in the [documentation](https://python-archinstall.readthedocs.io/en/latest/archinstall/Profile.html))*.

> **Creating your own ISO with this script on it:** Follow [ArchISO](https://wiki.archlinux.org/index.php/archiso)'s guide on how to create your own ISO or use a pre-built [guided ISO](https://hvornum.se/archiso/) to skip the python installation step, or to create auto-installing ISO templates. Further down are examples and cheat sheets on how to create different live ISO's.

# Help

Submit an issue on Github, or submit a post in the discord help channel.<br>
When doing so, attach any `install-session_*.log` to the issue ticket which can be found under `~/.cache/archinstall/`.

# Testing

## Using a Live ISO Image

If you want to test a commit, branch or bleeding edge release from the repository using the vanilla Arch Live ISO image, you can replace the version of archinstall with a new version and run that with the steps described below.

 1. You need a working network connection
 2. Install the build requirements with `pacman -Sy; pacman -S git python-pip`
    *(note that this may or may not work depending on your RAM and current state of the squashfs maximum filesystem free space)*
 3. Uninstall the previous version of archinstall with `pip uninstall archinstall`
 4. Now clone the latest repository with `git clone https://github.com/archlinux/archinstall`
 5. Enter the repository with `cd archinstall`
    *At this stage, you can choose to check out a feature branch for instance with `git checkout torxed-v2.2.0`*
 6. Build the project and install it using `python setup.py install`

After this, running archinstall with `python -m archinstall` will run against whatever branch you chose in step 5.

## Without a Live ISO Image

To test this without a live ISO, the simplest approach is to use a local image and create a loop device.<br>
This can be done by installing `pacman -S arch-install-scripts util-linux` locally and doing the following:

    # dd if=/dev/zero of=./testimage.img bs=1G count=5
    # losetup -fP ./testimage.img
    # losetup -a | grep "testimage.img" | awk -F ":" '{print $1}'
    # pip install --upgrade archinstall
    # python -m archinstall guided
    # qemu-system-x86_64 -enable-kvm -machine q35,accel=kvm -device intel-iommu -cpu host -m 4096 -boot order=d -drive file=./testimage.img,format=raw -drive if=pflash,format=raw,readonly,file=/usr/share/ovmf/x64/OVMF_CODE.fd -drive if=pflash,format=raw,readonly,file=/usr/share/ovmf/x64/OVMF_VARS.fd

This will create a *5GB* `testimage.img` and create a loop device which we can use to format and install to.<br>
`archinstall` is installed and executed in [guided mode](#docs-todo). Once the installation is complete,<br>
~~you can use qemu/kvm to boot the test media.~~ *(You'd actually need to do some EFI magic in order to point the EFI vars to the partition 0 in the test medium so this won't work entirely out of the box, but gives you a general idea of what we're going for here)*

There's also a [Building and Testing](https://github.com/archlinux/archinstall/wiki/Building-and-Testing) guide.<br>
It will go through everything from packaging, building and running *(with qemu)* the installer against a dev branch.
