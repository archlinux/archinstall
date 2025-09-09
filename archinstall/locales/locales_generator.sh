#!/usr/bin/env bash
set -euo pipefail

cd $(dirname "$0")/..

function update_lang() {
	file=${1}

	echo "Updating: ${file}"
	path=$(dirname "${file}")
	msgmerge --quiet --no-location --width 512 --backup none --update "${file}" locales/base.pot
	msgfmt -o "${path}/base.mo" "${file}"
}


function generate_all() {
	for file in $(find locales/ -name "base.po"); do
		update_lang "${file}"
	done
}

function generate_single_lang() {
	lang_file="locales/${1}/LC_MESSAGES/base.po"

	if [ ! -f "${lang_file}" ]; then
		echo "Language files not found: ${lang_file}"
		exit 1
	fi

	update_lang "${lang_file}"
}


if [ $# -eq 0 ]; then
	echo "Usage: ${0} <language_abbr>"
	echo "Special case 'all' for <language_abbr> builds all languages."
	exit 1
fi

lang=${1}

# Update the base file containing all translatable strings
find . -type f -iname "*.py" | xargs xgettext --join-existing --no-location --omit-header --keyword='tr' -d base -o locales/base.pot

case "${lang}" in
	"all") generate_all;;
	*) generate_single_lang "${lang}"
esac
