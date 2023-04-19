#!/bin/bash

zprofile="/tmp/archlive/airootfs/root/.zprofile"

mkdir -p /tmp/archlive/airootfs/root/archinstall-git
cp -r . /tmp/archlive/airootfs/root/archinstall-git

echo "pip uninstall archinstall -y" > $zprofile
echo "cd archinstall-git" >> $zprofile
echo "rm -rf dist" >> $zprofile

echo "python -m build --wheel --no-isolation" >> $zprofile
echo "pip install dist/archinstall*.whl" >> $zprofile

echo "echo \"This is an unofficial ISO for development and testing of archinstall. No support will be provided.\"" >> $zprofile
echo "echo \"This ISO was built from Git SHA $GITHUB_SHA\"" >> $zprofile
echo "echo \"Type archinstall to launch the installer.\"" >> $zprofile

cat $zprofile

pacman -Sy
pacman --noconfirm -S git archiso

cp -r /usr/share/archiso/configs/releng/* /tmp/archlive

echo -e "git\npython\npython-pip\npython-build\npython-flit\npython-setuptools\npython-wheel\npython-pyparted" >> /tmp/archlive/packages.x86_64

find /tmp/archlive
cd /tmp/archlive

mkarchiso -v -w work/ -o out/ ./
