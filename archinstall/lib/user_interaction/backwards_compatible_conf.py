from __future__ import annotations

import logging
import sys
from collections.abc import Iterable
from typing import Any, Union, TYPE_CHECKING

from ..exceptions import RequirementError
from ..menu import Menu
from ..output import log

if TYPE_CHECKING:
	_: Any


def generic_select(
		p_options: Union[list, dict],
		input_text: str = '',
		allow_empty_input: bool = True,
		options_output: bool = True,  # function not available
		sort: bool = False,
		multi: bool = False,
		default: Any = None) -> Any:
	"""
	A generic select function that does not output anything
	other than the options and their indexes. As an example:

	generic_select(["first", "second", "third option"])
		> first
		second
		third option
	When the user has entered the option correctly,
	this function returns an item from list, a string, or None

	Options can be any iterable.
	Duplicate entries are not checked, but the results with them are unreliable. Which element to choose from the duplicates depends on the return of the index()
	Default value if not on the list of options will be added as the first element
	sort will be handled by Menu()
	"""
	# We check that the options are iterable. If not we abort. Else we copy them to lists
	# it options is a dictionary we use the values as entries of the list
	# if options is a string object, each character becomes an entry
	# if options is a list, we implictily build a copy to maintain immutability
	if not isinstance(p_options, Iterable):
		log(f"Objects of type {type(p_options)} is not iterable, and are not supported at generic_select", fg="red")
		log(f"invalid parameter at Menu() call was at <{sys._getframe(1).f_code.co_name}>", level=logging.WARNING)
		raise RequirementError("generic_select() requires an iterable as option.")

	input_text = input_text if input_text else _('Select one of the values shown below: ')

	if isinstance(p_options, dict):
		options = list(p_options.values())
	else:
		options = list(p_options)
	# check that the default value is in the list. If not it will become the first entry
	if default and default not in options:
		options.insert(0, default)

	# one of the drawbacks of the new interface is that in only allows string like options, so we do a conversion
	# also for the default value if it exists
	soptions = list(map(str, options))
	default_value = options[options.index(default)] if default else None

	selected_option = Menu(input_text,
							soptions,
							skip=allow_empty_input,
							multi=multi,
							default_option=default_value,
							sort=sort).run()
	# we return the original objects, not the strings.
	# options is the list with the original objects and soptions the list with the string values
	# thru the map, we get from the value selected in soptions it index, and thu it the original object
	if not selected_option:
		return selected_option
	elif isinstance(selected_option, list):  # for multi True
		selected_option = list(map(lambda x: options[soptions.index(x)], selected_option))
	else:  # for multi False
		selected_option = options[soptions.index(selected_option)]
	return selected_option


def generic_multi_select(p_options: Union[list, dict],
							text: str = '',
							sort: bool = False,
							default: Any = None,
							allow_empty: bool = False) -> Any:

	text = text if text else _("Select one or more of the options below: ")

	return generic_select(p_options,
							input_text=text,
							allow_empty_input=allow_empty,
							sort=sort,
							multi=True,
							default=default)
