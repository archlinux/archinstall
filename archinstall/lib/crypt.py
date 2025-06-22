import base64
import ctypes
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id

from .output import debug

libcrypt = ctypes.CDLL('libcrypt.so')

libcrypt.crypt.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
libcrypt.crypt.restype = ctypes.c_char_p

libcrypt.crypt_gensalt.argtypes = [ctypes.c_char_p, ctypes.c_ulong, ctypes.c_char_p, ctypes.c_int]
libcrypt.crypt_gensalt.restype = ctypes.c_char_p

LOGIN_DEFS = Path('/etc/login.defs')


def _search_login_defs(key: str) -> str | None:
	defs = LOGIN_DEFS.read_text()
	for line in defs.split('\n'):
		line = line.strip()

		if line.startswith('#'):
			continue

		if line.startswith(key):
			value = line.split(' ')[1]
			return value

	return None


def crypt_gen_salt(prefix: str | bytes, rounds: int) -> bytes:
	if isinstance(prefix, str):
		prefix = prefix.encode('utf-8')

	setting = libcrypt.crypt_gensalt(prefix, rounds, None, 0)

	if setting is None:
		raise ValueError(f'crypt_gensalt() returned NULL for prefix {prefix!r} and rounds {rounds}')

	return setting


def crypt_yescrypt(plaintext: str) -> str:
	"""
	By default chpasswd in Arch uses PAM to to hash the password with crypt_yescrypt
	the PAM code https://github.com/linux-pam/linux-pam/blob/master/modules/pam_unix/support.c
	shows that the hashing rounds are determined from YESCRYPT_COST_FACTOR in /etc/login.defs
	If no value was specified (or commented out) a default of 5 is choosen
	"""
	value = _search_login_defs('YESCRYPT_COST_FACTOR')
	if value is not None:
		rounds = int(value)
		if rounds < 3:
			rounds = 3
		elif rounds > 11:
			rounds = 11
	else:
		rounds = 5

	debug(f'Creating yescrypt hash with rounds {rounds}')

	enc_plaintext = plaintext.encode('utf-8')
	salt = crypt_gen_salt('$y$', rounds)

	crypt_hash = libcrypt.crypt(enc_plaintext, salt)

	if crypt_hash is None:
		raise ValueError('crypt() returned NULL')

	return crypt_hash.decode('utf-8')


def _get_fernet(salt: bytes, password: str) -> Fernet:
	# https://cryptography.io/en/latest/hazmat/primitives/key-derivation-functions/#argon2id
	kdf = Argon2id(
		salt=salt,
		length=32,
		iterations=1,
		lanes=4,
		memory_cost=64 * 1024,
		ad=None,
		secret=None,
	)

	key = base64.urlsafe_b64encode(
		kdf.derive(
			password.encode('utf-8'),
		),
	)

	return Fernet(key)


def encrypt(password: str, data: str) -> str:
	salt = os.urandom(16)
	f = _get_fernet(salt, password)
	token = f.encrypt(data.encode('utf-8'))

	encoded_token = base64.urlsafe_b64encode(token).decode('utf-8')
	encoded_salt = base64.urlsafe_b64encode(salt).decode('utf-8')

	return f'$argon2id${encoded_salt}${encoded_token}'


def decrypt(data: str, password: str) -> str:
	_, algo, encoded_salt, encoded_token = data.split('$')
	salt = base64.urlsafe_b64decode(encoded_salt)
	token = base64.urlsafe_b64decode(encoded_token)

	if algo != 'argon2id':
		raise ValueError(f'Unsupported algorithm {algo!r}')

	f = _get_fernet(salt, password)
	try:
		decrypted = f.decrypt(token)
	except InvalidToken:
		raise ValueError('Invalid password')

	return decrypted.decode('utf-8')
