# archinstall
Just a bare bone automated [Arch](https://wiki.archlinux.org/index.php/Arch_Linux) install with network deployment instructions based on MAC-address.

# Autorun on Arch Live CD (Unattended install)

    # cd ~/archlive
    # echo -e "git\npython-psutil" >> packages.both
    # cat <<EOF >> ./airootfs/root/customize_airootfs.sh
    cd /root
    git clone https://github.com/Torxed/archinstall.git
    chmod +x ~/archinstall/archinstall.py
    EOF
    # mkdir ./airootfs/etc/skel
    # echo '[[ -z $DISPLAY && $XDG_VTNR -eq 1 ]] && sh -c "~/archinstall/archinstall.py"' >> ./airootfs/etc/skel/.zprofile
    
    # rm -v work*; ./build.sh -v
> Note: `~/archlive` might be different on your system, see [ArchISO#Setup](https://wiki.archlinux.org/index.php/archiso#Setup) for more info.

Whenever this live-cd boots, from here on now - it'll run `archinstall.py` and attempt to unattendely install a default Arch Linux base OS with `base base-devel` as packages.
Or - if successfull - a profile was found at [/deployments](https://github.com/Torxed/archinstall/tree/master/deployments) for the machine being installed (MAC-address based lookup).

> CAUTION: If no parameters are given, **it will devour the first disk in your system** (/dev/sda, /dev/nvme0n1 etc).

## Autorun on Arch Live CD (User specified profile)

Everything in the steps above are the same, except for one line that needs to change:

    # echo '[[ -z $DISPLAY && $XDG_VTNR -eq 1 ]] && sh -c "~/archinstall/archinstall.py --no-default"' >> ./airootfs/etc/skel/.zprofile

This will cause the script to halt and ask for a profile to install before proceeding.
When asked, enter `workstation` for instance - to install based on the workstation template.

> CAUTION: Even if `--no-default` is given, if a MAC-address matches under `/deployments`, that profile will forcefully be installed.

## Autorun on Arch Live CD (With custom webserver for deployment profiles)

Again, one line differs from the unattended install, change the following line:

    # echo '[[ -z $DISPLAY && $XDG_VTNR -eq 1 ]] && sh -c "~/archinstall/archinstall.py --profiles-path=http://example.com/profiles"' >> ./airootfs/etc/skel/.zprofile

This will cause the script to look at `http://example.com/profiles/<mac>.json` for instructions.

# Manually run it on a booted Live CD

    # wget https://raw.githubusercontent.com/Torxed/archinstall/master/archinstall.py
    # python3 archinstall.py

# Rerunning a installation

    # umount -R /mnt; cryptsetup close /dev/mapper/luksdev
    # python3 ./archinstall/archinstall.py
> Note: This assumes `--post=stay` is set to avoid instant reboot at the end or if during any time a user pressed `Ctrl-C` and aborted the installation.

# Some parameters you can give it

    --drive=</dev/sdX>
      Which drive to install arch on, if absent, the first disk under /dev/ is used
    
    --size=100% (Default)
      Sets the size of the root filesystem (btrfs)
    
    --start=513MiB (Default)
      Sets the starting location of the root partition
      (TODO: /boot will take up space from 1MiB - <start>, make sure boot is no larger than 513MiB)
    
    --password=0000 (Default)
      Which disk password to use, --password="<STDIN>" for prompt of password.

    --pwfile=/tmp/diskpw (Default)
      Which file to store the disk encryption password while sending it to cryptsetup
    
    --hostname=Arcinstall (Default)
      Sets the hostname of the box
    
    --country=SE (Default)
      Default mirror allocation for fetching packages.
    
    --packages='' (Default)
      Which additional packages to install, defaults to none.
      (Space separated as it's passed unchanged to `pacstrap`
    
    --user=<name>
      Adds an additional username to the system (default group Wheel)
    
    --post=reboot (Default)
      After a successful install, reboots into the system. Use --post=stay to not reboot.

    --no-default
      This parameter causes the installation script to halt if no MAC-based profile was found under /deployments

    --profiles-path=https://example.com/profiles
      Changes the default path the script looks for deployment profiles.
      The default path is 'https://raw.githubusercontent.com/Torxed/archinstall/master/deployments'

Deployment profile structs support all the above parameters and more, for instance, custom arguments with string formatting.
See [deployments/workstation.json](https://github.com/Torxed/archinstall/blob/net-deploy/deployments/workstation.json) for examples.

## End note

 ![description](description.jpg)
