# <img src="https://github.com/Torxed/archinstall/raw/master/docs/logo.png" alt="drawing" width="200"/>
Just another guided/automated [Arch Linux](https://wiki.archlinux.org/index.php/Arch_Linux) installer with a twist.
The installer also doubles as a python library to access each individual installation step for customized installs.

Pre-built ISO's can be found here which autostarts archinstall *(in a safe guided mode)*: https://hvornum.se/archiso/

 * archinstall [discord](https://discord.gg/cqXU88y) server
 * ~~archinstall [documentation](#)~~ *(TBA)*
 * archinstall ISO's: https://hvornum.se/archiso/
 * archinstall on [#archinstall@freenode (IRC)](irc://#archinstall@FreeNode)

# Installation & Usage

## Run as stand-alone binary on Live-CD

    # curl -L https://gzip.app/archinstall > archinstall.tar.gz
    # tar xvzf archinstall.tar.gz
    # cd archinstall-v2.0.3
    # chmod +x archinstall
    # ./archinstall

This downloads and runs a *compiled (using nuitka3)* version of the project.<br>
It will ask fora disk and start a guided installation.

## Install with `pacman` on Live-CD

    # curl -L https://gzip.app/archinstall.xz > archinstall.pkg.tar.xz
    # pacman -U archinstall.pkg.tar.xz
    # archinstall guided

This requires that the RAM on your machine is sufficient for a installation *(tested on 1024MB of RAM)*.<br>
But this will utilize `pacman` to install the pre-compiled binary from above and place archinstall in `PATH`.

## Install Python on Live-CD and run manually:

    # wget https://github.com/Torxed/archinstall/archive/v2.0.3.tar.gz
    # tar xvzf v2.0.2.tar.gz
    # cd archinstall-2.0.2
    # pacman -S --noconfirm python; python examples/guided.py

This will ask for a disk and start a guided installation.

## Install using `pip` and run as a Python module:

    # pip install archinstall
    # python -m archinstall guided

This assumes tho that `python >= 3.8` and `pip` is present *(not always the case on the default Arch Linux ISO)*, see above for pre-built ISO's containing Python+pip or follow the [docs](docs/) to see how to build an ISO yourself.

## Scripting an installation to put on a ISO media

Assuming you're building your own ISO and want to create an automated install process.<br>
This is probably what you'll need, a [minimal example](examples/main_example.py) of how to install using archinstall as a Python library.

```python
import archinstall, getpass

# Select a harddrive and a disk password
harddrive = archinstall.select_disk(archinstall.all_disks())
disk_password = getpass.getpass(prompt='Disk password (won\'t echo): ')

with archinstall.Filesystem(harddrive, archinstall.GPT) as fs:
    # use_entire_disk() is a helper to not have to format manually
    fs.use_entire_disk('luks2')

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
 * Proceed to wipe the selected disk with a `GPT` partition table.
 * Sets up a default 100% used disk with encryption.
 * Installs a basic instance of Arch Linux *(base base-devel linux linux-firmware btrfs-progs efibootmgr)*
 * Installs and configures a bootloader to partition 0.
 * Install additional packages *(nano, wget, git)*
 * Installs a network-profile called [workstation](https://github.com/Torxed/archinstall/blob/master/profiles/workstation.json) *(more on network profiles in the docs)*
 * Adds AUR support by compiling and installing [yay](https://github.com/Jguer/yay)

> **Creating your own ISO with this script on it:** Follow [ArchISO](https://wiki.archlinux.org/index.php/archiso)'s guide on how to create your own ISO or use a pre-built [guided ISO](https://hvornum.se/archiso/) to skip the python installation step, or to create auto-installing ISO templates. Further down are examples and cheat sheets on how to create different live ISO's.

# Testing

To test this without a live ISO, the simplest approach is to use a local image and create a loop device.<br>
This can be done by installing `pacman -S arch-install-scripts util-linux` locally and doing the following:

    # dd if=/dev/zero of=./testimage.img bs=1G count=5
    # losetup -fP ./testimage.img
    # losetup -a | grep "testimage.img" | awk -F ":" '{print $1}'
    # pip install archinstall
    # python -m archinstall guided
    # qemu-system-x86_64 -enable-kvm -machine q35,accel=kvm -device intel-iommu -cpu host -m 4096 -boot order=d -drive file=./testimage.img,format=raw -drive if=pflash,format=raw,readonly,file=/usr/share/ovmf/x64/OVMF_CODE.fd -drive if=pflash,format=raw,readonly,file=/usr/share/ovmf/x64/OVMF_VARS.fd

This will create a *5GB* `testimage.img` and create a loop device which we can use to format and install to.<br>
`archinstall` is installed and executed in [guided mode](#docs-todo). Once the installation is complete,<br>
~~you can use qemu/kvm to boot the test media.~~ *(You'd actually need to do some EFI magic in order to point the EFI vars to the partition 0 in the test medium so this won't work entirely out of the box, but gives you a general idea of what we're going for here)*

You can also run a pre-built ISO with pip and python

    # qemu-system-x86_64 -enable-kvm -cdrom /home/user/Downloads/archinstall-2020.07.08-x86_64.iso -machine q35,accel=kvm -device intel-iommu -cpu host -m 4096 -boot order=d -drive file=./testimage.img,format=raw -drive if=pflash,format=raw,readonly,file=/usr/share/ovmf/x64/OVMF_CODE.fd -drive if=pflash,format=raw,readonly,file=/usr/share/ovmf/x64/OVMF_VARS.fd

and once inside, just do

    # python -m archlinux guided

## End note

![description](https://github.com/Torxed/archinstall/raw/master/docs/description.jpg)
