import pytest

from archinstall.lib.models.users import PasswordStrength


@pytest.mark.parametrize(
	'password, expected',
	[
		('abc', PasswordStrength.VERY_WEAK),
		('Abcdef1!', PasswordStrength.WEAK),
		('Abcdef1234!', PasswordStrength.MODERATE),
		('Abcdef12345!@', PasswordStrength.STRONG),
		('', PasswordStrength.VERY_WEAK),
		('123456789', PasswordStrength.VERY_WEAK),
		('abcdefghijklmnopqr', PasswordStrength.STRONG),
	],
)
def test_password_strength(password: str, expected: PasswordStrength) -> None:
	assert PasswordStrength.strength(password) == expected
