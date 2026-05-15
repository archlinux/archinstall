from archinstall.tui.rich import BaseRichTable


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
