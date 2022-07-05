import logging
import os
import sys
from pathlib import Path
from typing import Dict, Union, List, Any
from pudb import set_trace
class FormattedOutput:

	@classmethod
	def values(cls, o: Any) -> Dict[str, Any]:
		if hasattr(o,'as_dict'):
			return o.as_dict()
		elif hasattr(o, 'as_json'):
			return o.as_json()
		elif hasattr(o, 'json'):
			return o.json()
		else:
			return o.__dict__

	@classmethod
	def as_table(cls, obj: List[Any]) -> str:
		column_width: Dict[str, int] = {}
		for o in obj:
			for k, v in cls.values(o).items():
				column_width.setdefault(k, 0)
				column_width[k] = max([column_width[k], len(str(v)), len(k)])

		output = ''
		for key, width in column_width.items():
			key = key.replace('!', '')
			output += key.ljust(width) + ' | '
		output = output[:-3] + '\n'
		output += '-' * len(output) + '\n'

		for o in obj:
			for k, v in cls.values(o).items():
				if '!' in k:
					v = '*' * len(str(v))
				output += str(v).ljust(column_width[k]) + ' | '
			output = output[:-3]
			output += '\n'

		return output

	@classmethod
	def as_table_filter(cls, obj: List[Any], field_formatter :Any = None, filter: List[str]) -> str:
		column_width: Dict[str, int] = {}
		for o in obj:
			for k, v in cls.values(o).items():
				# TODO field_formatter is called twice. ought to be called only once
				if field_formatter:
					v = field_formatter(o,k,v)
				column_width.setdefault(k, 0)
				column_width[k] = max([column_width[k], len(str(v)), len(k)])

		output = ''
		key_list = []
		for key in filter:
			width = column_width.get(key,len(key))
			key = key.replace('!', '')
			key_list.append(key.ljust(width))
		output += ' | '.join(key_list) +'\n'
		output += '-' * len(output) + '\n'

		for o in obj:
			obj_data = []
			for key in filter:
				width = column_width.get(key, len(key))
				# hasattr gives false positives, so i went for the primitive
				try:
					value = getattr(o,key)
				except AttributeError:
					value = ''
				if '!' in key:
					value = '*' * width
				obj_data.append(str(value).ljust(width))
			output += ' | '.join(obj_data) +'\n'

		return output
