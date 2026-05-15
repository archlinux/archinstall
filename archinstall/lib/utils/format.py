from collections.abc import Callable
from dataclasses import asdict, is_dataclass
from typing import TYPE_CHECKING, Any

from archinstall.lib.utils.encoding import unicode_ljust, unicode_rjust
from archinstall.tui.rich import BaseRichTable

if TYPE_CHECKING:
	from _typeshed import DataclassInstance


def as_key_value_pair(
	entries: dict[str, str | list[str] | bool],
	ignore_empty: bool = True,
) -> str:
	"""
	Formats key-values as a Rich Table:
		key1	: value1
		key2	: value2
	...
	"""
	table = BaseRichTable()
	table.add_column('key', style='bold', no_wrap=True)
	table.add_column('value', style='white', max_width=70)

	for label, value in entries.items():
		if ignore_empty and not value:
			continue

		if isinstance(value, bool):
			value = 'Yes' if value else 'No'

		if isinstance(value, list):
			value = '\n  '.join(str(val) for val in value)

		table.add_row(label.title(), f': {value}')

	return table.stringify()


def as_columns(entries: list[str], cols: int) -> str:
	"""
	Will format a list into a given number of columns
	"""
	chunks: list[list[str]] = []
	output = ''

	for i in range(0, len(entries), cols):
		chunks.append(entries[i : i + cols])

	for row in chunks:
		out_fmt = '{: <30} ' * len(row)
		output += out_fmt.format(*row) + '\n'

	return output


def _get_values(
	o: DataclassInstance,
	class_formatter: str | Callable | None = None,  # type: ignore[type-arg]  # pyright: ignore[reportMissingTypeArgument]
	filter_list: list[str] = [],
) -> dict[str, Any]:
	"""
	the original values returned a dataclass as dict thru the call to some specific methods
	this version allows thru the parameter class_formatter to call a dynamically selected formatting method.
	Can transmit a filter list to the class_formatter,
	"""
	if class_formatter:
		# if invoked per reference it has to be a standard function or a classmethod.
		# A method of an instance does not make sense
		if callable(class_formatter):
			return class_formatter(o, filter_list)
		# if is invoked by name we restrict it to a method of the class. No need to mess more
		elif hasattr(o, class_formatter) and callable(getattr(o, class_formatter)):
			func = getattr(o, class_formatter)
			return func(filter_list)

		raise ValueError('Unsupported formatting call')
	elif hasattr(o, 'table_data'):
		return o.table_data()
	elif hasattr(o, 'json'):
		return o.json()
	elif is_dataclass(o):
		return asdict(o)
	else:
		return o.__dict__  # type: ignore[unreachable]


def as_table(
	obj: list[Any],
	class_formatter: str | Callable | None = None,  # type: ignore[type-arg]
	filter_list: list[str] = [],
	capitalize: bool = False,
) -> str:
	"""variant of as_table (subtly different code) which has two additional parameters
	filter which is a list of fields which will be shown
	class_formatter a special method to format the outgoing data

	A general comment, the format selected for the output (a string where every data record is separated by newline)
	is for compatibility with a print statement
	As_table_filter can be a drop in replacement for as_table
	"""
	raw_data = [_get_values(o, class_formatter, filter_list) for o in obj]

	# determine the maximum column size
	column_width: dict[str, int] = {}
	for o in raw_data:
		for k, v in o.items():
			if not filter_list or k in filter_list:
				column_width.setdefault(k, 0)
				column_width[k] = max([column_width[k], len(str(v)), len(k)])

	if not filter_list:
		filter_list = list(column_width.keys())

	# create the header lines
	output = ''
	key_list = []
	for key in filter_list:
		width = column_width[key]
		key = key.replace('!', '').replace('_', ' ')

		if capitalize:
			key = key.capitalize()

		key_list.append(unicode_ljust(key, width))

	output += ' | '.join(key_list) + '\n'
	output += '-' * len(output) + '\n'

	# create the data lines
	for record in raw_data:
		obj_data = []
		for key in filter_list:
			width = column_width.get(key, len(key))
			value = record.get(key, '')

			if '!' in key:
				value = '*' * len(value)

			if isinstance(value, (int, float)) or (isinstance(value, str) and value.isnumeric()):
				obj_data.append(unicode_rjust(str(value), width))
			else:
				obj_data.append(unicode_ljust(str(value), width))

		output += ' | '.join(obj_data) + '\n'

	return output
