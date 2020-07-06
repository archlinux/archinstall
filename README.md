# <img src="https://github.com/Torxed/archinstall/raw/master/docs/logo.png" alt="drawing" width="200"/>
Just another guided/automated [Arch Linux](https://wiki.archlinux.org/index.php/Arch_Linux) installer with a twist.
The installer also doubles as a python library to access each individual installation step for customized installs.

Pre-built ISO's can be found here which autostarts archinstall *(in a safe guided mode)*: https://hvornum.se/archiso/

 * archinstall [discord](https://discord.gg/cqXU88y) server
 * archinstall guided install ISO's: https://hvornum.se/archiso/
 * archinstall on [#archinstall@freenode (IRC)](irc://#archinstall@FreeNode)

# Usage

## Run on Live-CD (Binary)

    # wget https://gzip.app/archinstall
    # chmod +x archinstall; ./archinstall

This downloads and runs a "compiled" *(using nuitka)* version of the project.<br>
It defaults to starting a guided install with some safety checks in place.

## Run on Live-CD with Python:

    # wget https://raw.githubusercontent.com/Torxed/archinstall/master/installer.py
    # pacman -S --noconfirm python; python install.py

This will start a guided install with the same safety checks as previous.<br>

## Run using PIP and Python module:

    # pip install archinstall
    # python -m archinstall

Again, a guided install starts with safety checks.<br>
This assumes tho that Python and Pip is present (not always the case on the default Arch Linux ISO), see above for pre-built ISO's containing Python+pip

## Scripting an installation

Assuming you're building your own ISO and want to create an automated install process.<br>
This is probably what you'll need, a minimal example of how to install using archinstall as a Python library.

```python
import archinstall, getpass

# Unmount and close previous runs
archinstall.sys_command(f'umount -R /mnt', surpress_errors=True)
archinstall.sys_command(f'cryptsetup close /dev/mapper/luksloop', surpress_errors=True)

# Select a harddrive and a disk password
harddrive = archinstall.select_disk(archinstall.all_disks())
disk_password = getpass.getpass(prompt='Disk password (won\'t echo): ')

with archinstall.Filesystem(harddrive, archinstall.GPT) as fs:
    # Use the entire disk instead of setting up partitions on your own
    fs.use_entire_disk('luks2')

    if harddrive.partition[1].size == '512M':
        raise OSError('Trying to encrypt the boot partition for petes sake..')
    harddrive.partition[0].format('fat32')

    with archinstall.luks2(harddrive.partition[1], 'luksloop', disk_password) as unlocked_device:
        unlocked_device.format('btrfs')
        
        with archinstall.Installer(unlocked_device, hostname='testmachine') as installation:
            if installation.minimal_installation():
                installation.add_bootloader(harddrive.partition[0])

                installation.add_additional_packages(['nano', 'wget', 'git'])
                installation.install_profile('workstation')

                installation.user_create('anton', 'test')
                installation.user_set_pw('root', 'toor')

                installation.add_AUR_support()
```

This installer will perform the following:

 * Prompt the user to select a disk and disk-password
 * Proceed to wipe said disk
 * Sets up a default 100% used disk with encryption
 * Installs a basic instance of Arch Linux *(base base-devel linux linux-firmware btrfs-progs efibootmgr)*
 * Installs and configures a bootloader
 * Install additional packages *(nano, wget, git)*
 * Installs a network-profile called `desktop` *(more on network profiles in the docs)*
 * Adds AUR support by compiling and installing [yay](https://github.com/Jguer/yay)

> **Creating your own ISO:** Follow [ArchISO](https://wiki.archlinux.org/index.php/archiso)'s guide on how to create your own ISO or use a pre-built [guided ISO](https://hvornum.se/archiso/) to skip the python installation step, or to create auto-installing ISO templates. Further down are examples and cheat sheets on how to create different live ISO's.

## End note

![description](https://github.com/Torxed/archinstall/raw/master/docs/description.jpg)