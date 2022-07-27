from archinstall.lib.output import log
from archinstall.lib.exceptions import UserError
# import pathlib
# import os
# from pprint import pprint
# from pudb import set_trace
# import logging
# from copy import deepcopy, copy
import re

from typing import Union

class LoopExit(BaseException):
	pass
def split_number_unit(value: Union[int,float,str]) -> (Union[float],str):
	""" from a number (whatever format) we return a tuple with its numeric value and the unit name (if present else 's')"""
	if isinstance(value,(int,float)):
		return value,'s'
	result = re.split(r'(\d+\.\d+|\d+)',value.replace(',','').strip())
	unit = result[2].lower().strip() if result[2].strip() else 's'
	target_value = float(result[1])
	return target_value,unit


def units_from_model(target: Union[int,float,str],model: Union[int,float,str]) -> Union[int,float,str]:
	""" we convert the value of target to the same numeric format as model has"""
	_,unit = split_number_unit(model)
	return convert_units(target,unit,'s')


def unit_best_fit(raw_value: Union[int,float,str], default_unit: str = 's', precision: int = 1) -> str:
	""" given an arbitrary value (numeric or numeric + unit) returns the equivalent value in units with the higher integer part """
	base_value = convert_units(raw_value,'s',default_unit)
	conversion_rates = {
		'KiB' : 2,
		'MiB' : 2**11,
		'GiB' : 2**21,
		'TiB' : 2**31,
	}
	for unit in ('TiB','GiB','MiB','KiB'):
		if base_value >= conversion_rates[unit]:
			return f"{convert_units(base_value,unit,'s',precision=precision)} {unit}"
	return f"{base_value} s"


def convert_units(
	value: Union[int,float,str],
	to_unit: str = 'b',
	d_from_unit: str = 'b',
	sector_size: int = 512,
	precision: int = 3
	) -> Union[int,float,str]:
	""" General routine to convert units
	parameters
	value is the one to be converted
	to_unit is the target unit (as default it will convert to sectors)
	from_unit. It the value lacks units (it's a pure number) determine which is the  unit it represents
	sector_size If sector size isnt't 512 you can specify which size to use
	precision  the number of decimal numbers it will return. If target are sectors or bytes it will always return an integer
	"""
	conversion_rates = {
		'kb' : 10**3,
		'mb' : 10**6,
		'gb' : 10**9,
		'tb' : 10**12,
		'kib' : 2**10,
		'mib' : 2**20,
		'gib' : 2**30,
		'tib' : 2**40,
		's' : sector_size
	}

	def to_bytes(number,unit):
		if unit == 'b':
			return number
		else:
			return number * conversion_rates[unit]

	def from_bytes(number,unit,precision=precision):
		if unit == 'b':
			return number
		if unit == 's':
			precision = 0
		return round(number / conversion_rates[unit],precision)

	if isinstance(value,(int,float)):
		target_value = value
		from_unit = d_from_unit.lower().strip() # if d_from_unit else 'b'
	else:
		result = re.split(r'(\d+\.\d+|\d+)',value.replace(',','').strip())
		from_unit = result[2].lower().strip() if result[2].strip() else d_from_unit
		target_value = float(result[1])

	to_unit = to_unit.lower().strip()

	if (from_unit == '%') or (to_unit == '%'):
		log(f"convert units does not support % notation")
		return value

	if from_unit in ('s','b','kib','mib','gib','tib','kb','mb','gb','tb'):
		pass
	else:
		raise UserError(f"Invalid use of {from_unit} as from unit in convert_units")
	if to_unit in ('s','b','kib','mib','gib','tib','kb','mb','gb','tb'):
		pass
	else:
		raise UserError(f"Invalid use of {to_unit} as to unit in convert_units")

	if to_unit == from_unit:
		return target_value
	if to_unit in ('s','b'):
		return int(round(from_bytes(to_bytes(target_value,from_unit),to_unit.strip().lower(),precision),0))
	else:
		return from_bytes(to_bytes(target_value,from_unit),to_unit.strip().lower(),precision)
