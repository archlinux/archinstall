#!/bin/bash

cd $(dirname "$0")/..

find . -type f -iname "*.py" | xargs xgettext -j --omit-header -d base -o locales/base.pot

for file in $(find locales/ -name "base.po"); do
	echo "Updating: $file"
	path=$(dirname $file)
	msgmerge --quiet --width 512 --update $file locales/base.pot
	msgfmt -o $path/base.mo $file
done
