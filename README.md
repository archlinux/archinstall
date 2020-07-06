# <img src="https://github.com/Torxed/archinstall/raw/annotations/docs/logo.png" alt="drawing" width="200"/>
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


hdd = archinstall.select_disk(archinstall.all_disks())
disk_password = getpass.getpass(prompt='Disk password (won\'t echo): ')

with archinstall.Filesystem(hdd, archinstall.GPT) as fs:
    fs.use_entire_disk('luks2')
    with archinstall.Luks2(fs) as crypt:
        if hdd.partition[1]['size'] == '512M':
            raise OSError('Trying to encrypt the boot partition for petes sake..')

        key_file = crypt.encrypt(hdd.partition[1], password=disk_password, key_size=512, hash_type='sha512', iter_time=10000, key_file='./pwfile')
        unlocked_crypt_vol = crypt.mount(hdd.partition[1], 'luksloop', key_file)

        with archinstall.Installer(unlocked_crypt_vol, hostname='testmachine') as installation:
            if installation.minimal_installation():
                installation.add_bootloader()

                installation.add_additional_packages(['nano', 'wget', 'git'])
                installation.install_profile('desktop')

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

![description](https://github.com/Torxed/archinstall/raw/annotations/docs/description.jpg)