import unicodedata
from functools import lru_cache


@lru_cache(maxsize=128)
def _is_wide_character(char: str) -> bool:
	return unicodedata.east_asian_width(char) in 'FW'


def _count_wchars(string: str) -> int:
	"Count the total number of wide characters contained in a string"
	return sum(_is_wide_character(c) for c in string)


def unicode_ljust(string: str, width: int, fillbyte: str = ' ') -> str:
	"""Return a left-justified unicode string of length width.
	>>> unicode_ljust('Hello', 15, '*')
	'Hello**********'
	>>> unicode_ljust('你好', 15, '*')
	'你好***********'
	>>> unicode_ljust('안녕하세요', 15, '*')
	'안녕하세요*****'
	>>> unicode_ljust('こんにちは', 15, '*')
	'こんにちは*****'
	"""
	return string.ljust(width - _count_wchars(string), fillbyte)


def unicode_rjust(string: str, width: int, fillbyte: str = ' ') -> str:
	"""Return a right-justified unicode string of length width.
	>>> unicode_rjust('Hello', 15, '*')
	'**********Hello'
	>>> unicode_rjust('你好', 15, '*')
	'***********你好'
	>>> unicode_rjust('안녕하세요', 15, '*')
	'*****안녕하세요'
	>>> unicode_rjust('こんにちは', 15, '*')
	'*****こんにちは'
	"""
	return string.rjust(width - _count_wchars(string), fillbyte)
