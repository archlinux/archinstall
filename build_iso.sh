#!/bin/bash

set -eu

readonly base_profile="/usr/share/archiso/configs/releng/"
readonly custom_profile="/tmp/archlive"
readonly packages_file="$custom_profile/packages.x86_64"
readonly airootfs="$custom_profile/airootfs"
readonly archinstall_dir="/root/archinstall"
readonly build_script="/root/build-archinstall.sh"
readonly build_service="/etc/systemd/system/build-archinstall.service"

# Packages to add to the archiso custom profile
packages=(
	git
	python
	python-pip
	python-build
	python-setuptools
	python-wheel
	python-pyparted
)

pacman -Sy
pacman --noconfirm -S git archiso

# Copy an archiso base profile to create a custom profile from
cp -r $base_profile $custom_profile

# Copy the archinstall directory to the archiso custom profile
cp -r "$(dirname "$0")" ${airootfs}${archinstall_dir}

# Remove the archinstall package from the archiso custom profile
sed -i /archinstall/d $packages_file

# Add packages to the archiso custom profile
for package in "${packages[@]}"; do
	echo "$package" >> $packages_file
done

# Use the `GITHUB_SHA` environment variable for the commit hash if it exists
if [[ -v GITHUB_SHA ]]; then
	commit_hash="$GITHUB_SHA"
# Use git for the commit hash if the `GITHUB_SHA` environment varible is not set
else
	commit_hash="$(git rev-parse HEAD)"
fi

# Append an archinstall developement message to motd
cat <<- _EOF_ >> $airootfs/etc/motd

	[1;31marchinstall development ISO[0m
	Git commit hash: $commit_hash
	This is an unofficial ISO for development and testing of archinstall. No support will be provided.
_EOF_

# A script to build archinstall in the live environment
cat <<- _EOF_ > ${airootfs}${build_script}
	cd $archinstall_dir
	rm -rf dist

	python -m build --wheel --no-isolation
	pip install dist/*.whl
_EOF_

# A service to run the archinstall build script in the live environment
cat <<- _EOF_ > ${airootfs}${build_service}
	[Unit]
	Description=Build archinstall
	After=network.target

	[Service]
	Type=oneshot
	ExecStart=/bin/sh $build_script

	[Install]
	WantedBy=multi-user.target
_EOF_

# Enable the service that runs the archinstall build script
ln -sf $build_service $airootfs/etc/systemd/system/multi-user.target.wants/

# A startup file to wait for the completion of the service that runs the archinstall build script
cat <<- _EOF_ > $airootfs/root/.zprofile
	if [ "\$(systemctl show -p SubState --value ${build_service##*/})" != "dead" ]; then
	    printf "Building archinstall (${build_service##*/})..."
	    while [ "\$(systemctl show -p SubState --value ${build_service##*/})" != "dead" ]; do
	        sleep 1
	    done
	    echo " done"
	    echo "Type [35marchinstall[0m to launch the installer."
	fi

	cd $archinstall_dir
_EOF_

cd $custom_profile

mkarchiso -v $custom_profile
