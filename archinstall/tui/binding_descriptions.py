"""Textual's built-in key binding descriptions, listed for xgettext.

These strings live inside the textual package, so xgettext cannot find them
when scanning this code base. At runtime _translate_bindings() in
components.py translates every binding description with tr(), including the
ones inherited from textual widgets - this module only makes those strings
visible to the extraction in locales_generator.sh (via the tr_noop keyword).

The list covers the MRO-merged bindings of the textual classes used in
components.py: _translate_bindings() operates on the merged bindings map, so
descriptions inherited from ancestors (e.g. Scroll Up from ScrollView) are
translated at runtime too and must be listed here.

Verify or regenerate the list after a textual upgrade or after introducing
a new textual widget in components.py:

	python3 test_tooling/check_binding_descriptions.py
"""

from archinstall.lib.translationhandler import tr_noop

# textual 8.2.8
TEXTUAL_BINDING_DESCRIPTIONS: tuple[str, ...] = (
	tr_noop('Bottom'),
	tr_noop('Copy selected text'),
	tr_noop('Cursor down'),
	tr_noop('Cursor left'),
	tr_noop('Cursor right'),
	tr_noop('Cursor up'),
	tr_noop('Cut selected text'),
	tr_noop('Delete all to the left'),
	tr_noop('Delete all to the right'),
	tr_noop('Delete character left'),
	tr_noop('Delete character right'),
	tr_noop('Delete left to start of word'),
	tr_noop('Delete right to start of word'),
	tr_noop('Down'),
	tr_noop('End'),
	tr_noop('First'),
	tr_noop('Focus Next'),
	tr_noop('Focus Previous'),
	tr_noop('Go to end'),
	tr_noop('Go to start'),
	tr_noop('Home'),
	tr_noop('Last'),
	tr_noop('Move cursor left'),
	tr_noop('Move cursor left a word'),
	tr_noop('Move cursor left a word and select'),
	tr_noop('Move cursor left and select'),
	tr_noop('Move cursor right a word'),
	tr_noop('Move cursor right a word and select'),
	tr_noop('Move cursor right and select'),
	tr_noop('Move cursor right or accept the completion suggestion'),
	tr_noop('Page Down'),
	tr_noop('Page Left'),
	tr_noop('Page Right'),
	tr_noop('Page Up'),
	tr_noop('Page down'),
	tr_noop('Page up'),
	tr_noop('Paste text from the clipboard'),
	tr_noop('Press button'),
	tr_noop('Quit'),
	tr_noop('Scroll Down'),
	tr_noop('Scroll End'),
	tr_noop('Scroll Home'),
	tr_noop('Scroll Left'),
	tr_noop('Scroll Right'),
	tr_noop('Scroll Up'),
	tr_noop('Select'),
	tr_noop('Select all'),
	tr_noop('Select line end'),
	tr_noop('Select line start'),
	tr_noop('Submit'),
	tr_noop('Toggle option'),
	tr_noop('Top'),
	tr_noop('Up'),
)
