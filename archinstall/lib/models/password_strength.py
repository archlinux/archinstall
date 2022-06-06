from enum import Enum


class PasswordStrength(Enum):
	VERY_WEAK = 'very weak'
	WEAK = 'weak'
	MODERATE = 'moderate'
	STRONG = 'strong'

	@property
	def value(self):
		match self:
			case PasswordStrength.VERY_WEAK: return str(_('very weak'))
			case PasswordStrength.WEAK: return str(_('weak'))
			case PasswordStrength.MODERATE: return str(_('moderate'))
			case PasswordStrength.STRONG: return str(_('strong'))

	def color(self):
		match self:
			case PasswordStrength.VERY_WEAK: return 'red'
			case PasswordStrength.WEAK: return 'red'
			case PasswordStrength.MODERATE: return 'yellow'
			case PasswordStrength.STRONG: return 'green'

	@classmethod
	def strength(cls, password: str) -> 'PasswordStrength':
		digit = any(character.isdigit() for character in password)
		upper = any(character.isupper() for character in password)
		lower = any(character.islower() for character in password)
		symbol = any(not character.isalnum() for character in password)
		return cls._check_password_strength(digit, upper, lower, symbol, len(password))

	@classmethod
	def _check_password_strength(
		cls,
		digit: bool,
		upper: bool,
		lower: bool,
		symbol: bool,
		length: int
	) -> 'PasswordStrength':
		# suggested evaluation
		# https://github.com/archlinux/archinstall/issues/1304#issuecomment-1146768163
		if digit and upper and lower and symbol:
			match length:
				case num if 13 <= num:
					return PasswordStrength.STRONG
				case num if 11 <= num <= 12:
					return PasswordStrength.MODERATE
				case num if 7 <= num <= 10:
					return PasswordStrength.WEAK
				case num if num <= 6:
					return PasswordStrength.VERY_WEAK
		elif digit and upper and lower:
			match length:
				case num if 14 <= num:
					return PasswordStrength.STRONG
				case num if 11 <= num <= 13:
					return PasswordStrength.MODERATE
				case num if 7 <= num <= 10:
					return PasswordStrength.WEAK
				case num if num <= 6:
					return PasswordStrength.VERY_WEAK
		elif upper and lower:
			match length:
				case num if 15 <= num:
					return PasswordStrength.STRONG
				case num if 12 <= num <= 14:
					return PasswordStrength.MODERATE
				case num if 7 <= num <= 11:
					return PasswordStrength.WEAK
				case num if num <= 6:
					return PasswordStrength.VERY_WEAK
		elif lower or upper:
			match length:
				case num if 18 <= num:
					return PasswordStrength.STRONG
				case num if 14 <= num <= 17:
					return PasswordStrength.MODERATE
				case num if 9 <= num <= 13:
					return PasswordStrength.WEAK
				case num if num <= 8:
					return PasswordStrength.VERY_WEAK

		return PasswordStrength.VERY_WEAK
