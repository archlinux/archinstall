# archinstall
Just a bare bone arch install

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

# Manually run it on a booted Live CD

    # git clone https://github.com/Torxed/archinstall.git
    # python3 ./archinstall/archinstall.py

# Some parameters you can give it

    WIP
