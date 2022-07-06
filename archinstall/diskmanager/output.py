from typing import Dict, List, Any

class FormattedOutput:

	@classmethod
	def values(cls, o: Any,class_formatter: str = None) -> Dict[str, Any]:
		# key must be a method of the class. JUst to avoid a  lot of complex code
		if hasattr(o, class_formatter) and callable(getattr(o, class_formatter)):
			func = getattr(o, class_formatter)
			return func()
		if hasattr(o,'as_dict_str'):
			return o.as_dict_str()
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
	def as_table_filter(cls, obj: List[Any], filter: List[str], class_formatter :str = None) -> str:
		column_width: Dict[str, int] = {}
		for o in obj:
			for k, v in cls.values(o,class_formatter).items():
				column_width.setdefault(k, 0)
				column_width[k] = max([column_width[k], len(str(v)), len(k)])

		output = ''
		key_list = []
		for key in filter:
			width = column_width.get(key,len(key))
			key = key.replace('!', '')
			key_list.append(key.ljust(width))
		output += ' | '.join(key_list) + '\n'
		output += '-' * len(output) + '\n'

		for o in obj:
			obj_data = []
			original_data = cls.values(o,class_formatter)
			for key in filter:
				width = column_width.get(key, len(key))
				# hasattr gives false positives, so i went for the primitive
				value = original_data.get(key,'')
				if '!' in key:
					value = '*' * width
				if value.isnumeric():
					obj_data.append(str(value).rjust(width))
				else:
					obj_data.append(str(value).ljust(width))
			output += ' | '.join(obj_data) + '\n'

		return output
