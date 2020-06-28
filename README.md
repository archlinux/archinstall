# <img src="logo.png" alt="drawing" width="200"/>
Just another guided/automated [Arch Linux](https://wiki.archlinux.org/index.php/Arch_Linux) installer.

Pre-built ISO's can be found here which autostarts this script *(in guided mode)*: https://hvornum.se/archiso/

# How-to / Usecases

## Run on Live-CD (Binary)

    # wget https://gzip.app/archinstall
    # chmod +x archinstall; ./archinstall

## Run on Live-CD (Python):

    # wget https://raw.githubusercontent.com/Torxed/archinstall/master/archinstall.py
    # pacman -S --noconfirm python; python archinstall.py

This will start a guided install.<br>
Add `--default` for a unattended minimalistic installation of Arch Linux.

> **Creating your own ISO:** Follow [ArchISO](https://wiki.archlinux.org/index.php/archiso)'s guide on how to create your own ISO or use a pre-built [guided ISO](https://hvornum.se/archiso/) to skip the python installation step, or to create auto-installing ISO templates. Further down are examples and cheat sheets on how to create different live ISO's.

# Features

 * User guided install of Arch Linux *(Like most other distros have)*
 * `AUR` package support.
 * Unattended install of Arch Linux
 * Profile / Template based installs
 * Full disk encryption, locale/region settings and customizable application selection
 * YubiKey support for disk and root password *(TBD / next release)*
 * <strike>Supports offline-installation of Arch Linux</strike>
 * Never creates or leave post-install/service scripts *(usually used to finalize databases etc)*

**Default Installation Contains:** Encrypts drive, btrfs filesystem, `linux` kernel, nano, wpa_supplicant *(and dialog)* 

# Examples:

 * `./archinstall --profile=workstation --drive=/dev/sda` - Installs the [workstation](https://github.com/Torxed/archinstall/blob/master/deployments/workstation.json) template on the drive `/dev/sda`

# [Build a Arch Linux ISO to autorun archinstall](https://github.com/Torxed/archinstall/wiki/Autorun-on-Arch-Live-CD)

More options for the built ISO:

### [Unattended install of a profile](https://github.com/Torxed/archinstall/wiki/Unattended-install-of-a-profile)

### [User guided install (DEFAULT)](https://github.com/Torxed/archinstall/wiki/User-guided-installation-(DEFAULT))

### [Custom web-server for deployment profiles](https://github.com/Torxed/archinstall/wiki/Custom-web-server-for-deployment-profiles)

### [Rerunning the installation](https://github.com/Torxed/archinstall/wiki/Rerunning-the-installation)

# Some parameters you can give it

    --drive=</dev/sdX>
      Which drive to install arch on, if absent, the first disk under /dev/ is used

    --minimal
    Starts a minimal installation, and skips looking for profiles.
    
    --size=100% (Default)
      Sets the size of the root filesystem (btrfs)
    
    --start=513MiB (Default)
      Sets the starting location of the root partition
      (TODO: /boot will take up space from 1MiB - <start>, make sure boot is no larger than 513MiB)
    
    --password=0000 (Default)
      Which disk password to use,
        --password="<STDIN>" for prompt of password
        --password="<YUBIKEY>" for setting a unique password on the YubiKey and use that as a password
        (NOTE: This will wipe/replace slot 1 on the YubiKey)

    --aur-support (default)

    --pwfile=/tmp/diskpw (Default)
      Which file to store the disk encryption password while sending it to cryptsetup
    
    --hostname=Arcinstall (Default)
      Sets the hostname of the box
    
    --country=all (Default)
      Default mirror allocation for fetching packages.
      If network is found, archinstall will try to attempt and guess which country the
      install originates from, basing it off GeoIP off your public IP (uses https://hvornu.se/ip/ for lookups)
    
    --packages='' (Default)
      Which additional packages to install, defaults to none.
      (Space separated as it's passed unchanged to `pacstrap`
    
    --user=<name>
      Adds an additional username to the system (default group Wheel)
    
    --post=reboot (Default)
      After a successful install, reboots into the system. Use --post=stay to not reboot.

    --unattended
      This parameter causes the installation script to install arch unattended on the first disk

    --profile=<name>
      For instance, --profile=workstation will install the workstation profile.

    --profiles-path=https://example.com/profiles
      Changes the default path the script looks for deployment profiles.
      The default path is 'https://raw.githubusercontent.com/Torxed/archinstall/master/deployments'

    --rerun="Name of step in profile"
      Enables you to skip the format, encryption and base install steps.
      And head straight for a step in the profile specified.
      (Useful for debugging a step in your profile)

    --localtime="Europe/Stockholm" (Default if --country=SE, otherwise GMT+0)
      Specify a localtime you're used to.

Deployment profile structs support all the above parameters and more, for instance, custom arguments with string formatting.
See [deployments/workstation.json](https://github.com/Torxed/archinstall/blob/net-deploy/deployments/workstation.json) for examples.

# Contact

IRC: `#archinstall@FreeNode`

## End note

 ![description](description.jpg)
