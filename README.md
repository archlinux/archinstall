# archinstall
Just a bare bone automated [Arch](https://wiki.archlinux.org/index.php/Arch_Linux) install with network deployment instructions based on MAC-address.

# Autorun on Arch Live CD

    # cd ~/archlive
    # echo -e "git\npython-psutil" >> packages.both
    # echo "git clone https://github.com/Torxed/archinstall.git" >> ./airootfs/root/customize_airootfs.sh
    # echo "chmod +x ~/archinstall/archinstall.py" >> ./airootfs/root/customize_airootfs.sh
    # mkdir ./airootfs/etc/skel
    # echo '[[ -z $DISPLAY && $XDG_VTNR -eq 1 ]] && sh -c ~/archinstall/archinstall.py' >> ./airootfs/etc/skel/.zprofile
    
    # rm -v work/build.make_* && ./build.sh -v
> Note: `~/archlive` might be different on your system, see [ArchISO#Setup](https://wiki.archlinux.org/index.php/archiso#Setup) for more info.

Whenever this live-cd boots, from here on now - it'll run `archinstall.py`.

> CAUTION: If no parameters are given, it will devour the first disk in your system (/dev/sda, /dev/nvme0n1p2 etc).

# Manually run it on a booted Live CD

    # git clone https://github.com/Torxed/archinstall.git
    # python3 ./archinstall/archinstall.py

# Some parameters you can give it

    --drive=</dev/sdX>
      Which drive to install arch on, if absent, the first disk under /dev/ is used
    
    --size=100% (Default)
      Sets the size of the root filesystem (btrfs)
    
    --start=513MiB (Default)
      Sets the starting location of the root partition
      (TODO: /boot will take up space from 1MiB - <start>, make sure boot is no larger than 513MiB)
    
    --pwfile=/tmp/diskpw (Default)
      Which file to use as the disk encryption password
    
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
      After a successful install, reboots into the system.

## End note

 ![description](description.jpg)
