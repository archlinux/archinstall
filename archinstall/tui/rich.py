from io import StringIO

from rich import box
from rich.console import Console
from rich.table import Table as RichTable


class BaseRichTable(RichTable):
	def __init__(self) -> None:
		super().__init__(
			box=box.SIMPLE,
			show_header=False,
			pad_edge=False,
			show_edge=False,
		)

	def stringify(self) -> str:
		string_io = StringIO()
		buf = Console(file=string_io, highlight=False)
		buf.print(self)

		_ = string_io.seek(0)
		output = string_io.read()

		return output
