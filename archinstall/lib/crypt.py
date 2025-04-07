import ctypes
import ctypes.util

libcrypt = ctypes.CDLL("libcrypt.so")

libcrypt.crypt.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
libcrypt.crypt.restype = ctypes.c_char_p

libcrypt.crypt_gensalt.argtypes = [ctypes.c_char_p, ctypes.c_ulong, ctypes.c_char_p, ctypes.c_int]
libcrypt.crypt_gensalt.restype = ctypes.c_char_p


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
	If no value was specified (or commented out) a default of 5 is choosen, given that the default
	/etc/login.defs file from the ISO has the variable commented out 5 would be the default value
	determined by the PAM in chpasswd
	"""
	rounds = 5

	enc_plaintext = plaintext.encode('utf-8')
	salt = crypt_gen_salt('$y$', rounds)

	crypt_hash = libcrypt.crypt(enc_plaintext, salt)

	if crypt_hash is None:
		raise ValueError('crypt() returned NULL')

	return crypt_hash.decode('utf-8')
