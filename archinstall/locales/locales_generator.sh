#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

usage() {
	echo "Usage: ${0} <command>"
	echo ""
	echo "Commands:"
	echo "  all         Regenerate base.pot and update all languages"
	echo "  <lang>      Regenerate base.pot and update a single language"
	echo "  check       Run translation validation checks"
	echo "  -h, --help  Show this help"
}

generate_pot() {
	# tr        - regular translation calls
	# tr_noop   - extraction-only marker for strings translated later from a variable
	# Binding:3 - the description argument of textual Binding() definitions,
	#             translated at runtime by _translate_bindings(). The description
	#             must be passed positionally - xgettext cannot see keyword arguments.
	find . -type f -iname '*.py' | sort \
		| xargs xgettext --no-location --omit-header \
			--keyword='tr' --keyword='tr_noop' --keyword='Binding:3' \
			-d base -o locales/base.pot
}

update_lang() {
	local file=${1}
	echo "Updating: ${file}"
	local path
	path=$(dirname "${file}")
	msgmerge --quiet --no-location --width 512 --backup none --update "${file}" locales/base.pot
	msgfmt -o "${path}/base.mo" "${file}"
}

cmd_generate_all() {
	generate_pot
	for file in $(find locales/ -name "base.po"); do
		update_lang "${file}"
	done
}

cmd_generate_single() {
	local lang_file="locales/${1}/LC_MESSAGES/base.po"
	if [ ! -f "${lang_file}" ]; then
		echo "Language files not found: ${lang_file}"
		exit 1
	fi
	generate_pot
	update_lang "${lang_file}"
}

cmd_check_po_syntax() {
	echo "Checking .po syntax..."
	local failed=0
	while IFS= read -r po; do
		if ! msgfmt --check --output-file=/dev/null "$po" 2>&1; then
			echo "FAIL: $po"
			failed=1
		fi
	done < <(find locales/ -name '*.po')
	if [ "$failed" -eq 1 ]; then
		echo "ERROR: some .po files have syntax errors" >&2
		return 1
	fi
	echo "All .po files passed syntax check."
}

cmd_check() {
	local failed=0
	cmd_check_po_syntax || failed=1
	if [ "$failed" -eq 1 ]; then
		echo "Some translation checks failed." >&2
		exit 1
	fi
	echo "All translation checks passed."
}

if [ $# -eq 0 ]; then
	usage
	exit 1
fi

case "${1}" in
	check)    cmd_check ;;
	all)      cmd_generate_all ;;
	-h|--help) usage ;;
	*)        cmd_generate_single "${1}" ;;
esac
