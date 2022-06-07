#!/bin/bash

cd $(dirname "$0")/..

find . -type f -iname "*.py" | xargs xgettext --join-existing --no-location --omit-header -d base -o locales/base.pot

for file in $(find locales/ -name "base.po"); do
	echo "Updating: $file"
	path=$(dirname $file)
	msgmerge --quiet --no-location --width 512 --backup none --update $file locales/base.pot
	msgfmt -o $path/base.mo $file
done
