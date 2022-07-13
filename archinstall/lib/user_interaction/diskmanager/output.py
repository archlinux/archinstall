from typing import Dict, List, Any
"""
this class is a copy of the original one for the project at archinstall/lib/output.py
The idea is to reintegrate the changes at the upstream if they are considered worth of generalizatin
"""
class FormattedOutput:

	@classmethod
	def values(cls, o: Any,class_formatter: str = None) -> Dict[str, Any]:
		""" the original values returned a dataclass as dict thru the call to some specific methods
		this version allows thru the parameter class_formatter to call a dynamicly selected formatting method
		"""
		# key must be a method of the class. JUst to avoid a  lot of complex code
		if class_formatter and hasattr(o, class_formatter) and callable(getattr(o, class_formatter)):
			func = getattr(o, class_formatter)
			return func()
		elif hasattr(o, 'as_json'):
			return o.as_json()
		elif hasattr(o, 'json'):
			return o.json()
		else:
			return o.__dict__

	@classmethod
	def as_table(cls, obj: List[Any], filter: List[str], class_formatter :str = None) -> str:
		""" variant of as_table (subtly different code) which has two additional parameters
		filter which is a list of fields which will be shon
		class_formatter a special method to format the outgoing data

		A general comment, the format selected for the output (a string where every data record is separated by newline)
		is for compatibility with a print statement
		As_table_filter can be a drop in replacement for as_table
		"""
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
				value = original_data.get(key,'')
				if '!' in key:
					value = '*' * width
				if isinstance(value,(int,float)) or (isinstance(value,str) and value.isnumeric()):
					obj_data.append(str(value).rjust(width))
				else:
					obj_data.append(str(value).ljust(width))
			output += ' | '.join(obj_data) + '\n'

		return output
