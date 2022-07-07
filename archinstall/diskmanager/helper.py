import archinstall
# import pathlib
# import os
# from pprint import pprint
# from pudb import set_trace
# import logging
# from copy import deepcopy, copy
import re

# from typing import Any, TYPE_CHECKING, Dict, Optional, List


def split_number_unit(value):
	result = re.split(r'(\d+\.\d+|\d+)',value.replace(',','').strip())
	unit = result[2].lower().strip() if result[2].strip() else 's'
	target_value = float(result[1])
	return target_value,unit

def unit_best_fit(raw_value,default_unit='s'):
	""" given an arbitrary value (numeric or numeric + unit) returns the equivalent value in units with the higher integer part """
	base_value = convert_units(raw_value,'s',default_unit)
	conversion_rates = {
		'KiB' : 2,
		'MiB' : 2**11,
		'GiB' : 2**21,
		'TiB' : 2**31,
	}
	for unit in ('TiB','GiB','MiB','KiB'):
		if base_value > conversion_rates[unit]:
			return f"{convert_units(base_value,unit,'s',precision=1)} {unit}"
	return f"{base_value} s"


def convert_units(value,to_unit='b',d_from_unit='b',sector_size=512,precision=3):
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
		archinstall.log(f"convert units does not support % notation")
		return value

	if from_unit in ('s','b','kib','mib','gib','tib','kb','mb','gb','tb'):
		pass
	else:
		raise archinstall.UserError(f"Invalid use of {from_unit} as from unit in convert_units")
	if to_unit in ('s','b','kib','mib','gib','tib','kb','mb','gb','tb'):
		pass
	else:
		raise archinstall.UserError(f"Invalid use of {to_unit} as to unit in convert_units")

	if to_unit == from_unit:
		return target_value
	if to_unit in ('s','b'):
		return int(round(from_bytes(to_bytes(target_value,from_unit),to_unit.strip().lower(),precision),0))
	else:
		return from_bytes(to_bytes(target_value,from_unit),to_unit.strip().lower(),precision)
