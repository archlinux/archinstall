import abc
import os
import sys
import logging
from .storage import storage

class LOG_LEVELS:
	Critical = 0b001
	Error = 0b010
	Warning = 0b011
	Info = 0b101
	Debug = 0b111

class journald(dict):
	@abc.abstractmethod
	def log(message, level=LOG_LEVELS.Debug):
		import systemd.journal
		log_adapter = logging.getLogger('archinstall')
		log_fmt = logging.Formatter("[%(levelname)s]: %(message)s")
		log_ch = systemd.journal.JournalHandler()
		log_ch.setFormatter(log_fmt)
		log_adapter.addHandler(log_ch)
		log_adapter.setLevel(logging.DEBUG)
		
		if level == LOG_LEVELS.Critical:
			log_adapter.critical(message)
		elif level == LOG_LEVELS.Error:
			log_adapter.error(message)
		elif level == LOG_LEVELS.Warning:
			log_adapter.warning(message)
		elif level == LOG_LEVELS.Info:
			log_adapter.info(message)
		elif level == LOG_LEVELS.Debug:
			log_adapter.debug(message)
		else:
			# Fallback logger
			log_adapter.debug(message)

# Found first reference here: https://stackoverflow.com/questions/7445658/how-to-detect-if-the-console-does-support-ansi-escape-codes-in-python
# And re-used this: https://github.com/django/django/blob/master/django/core/management/color.py#L12
def supports_color():
	"""
	Return True if the running system's terminal supports color,
	and False otherwise.
	"""
	supported_platform = sys.platform != 'win32' or 'ANSICON' in os.environ

	# isatty is not always implemented, #6223.
	is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
	return supported_platform and is_a_tty

# Heavily influenced by: https://github.com/django/django/blob/ae8338daf34fd746771e0678081999b656177bae/django/utils/termcolors.py#L13
# Color options here: https://askubuntu.com/questions/528928/how-to-do-underline-bold-italic-strikethrough-color-background-and-size-i
def stylize_output(text :str, *opts, **kwargs):
	opt_dict = {'bold': '1', 'italic' : '3', 'underscore': '4', 'blink': '5', 'reverse': '7', 'conceal': '8'}
	color_names = ('black', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white')
	foreground = {color_names[x]: '3%s' % x for x in range(8)}
	background = {color_names[x]: '4%s' % x for x in range(8)}
	RESET = '0'

	code_list = []
	if text == '' and len(opts) == 1 and opts[0] == 'reset':
		return '\x1b[%sm' % RESET
	for k, v in kwargs.items():
		if k == 'fg':
			code_list.append(foreground[v])
		elif k == 'bg':
			code_list.append(background[v])
	for o in opts:
		if o in opt_dict:
			code_list.append(opt_dict[o])
	if 'noreset' not in opts:
		text = '%s\x1b[%sm' % (text or '', RESET)
	return '%s%s' % (('\x1b[%sm' % ';'.join(code_list)), text or '')

def log(*args, **kwargs):
	string = orig_string = ' '.join([str(x) for x in args])

	if supports_color():
		kwargs = {'bg' : 'black', 'fg': 'white', **kwargs}
		string = stylize_output(string, **kwargs)

	if (logfile := storage.get('logfile', None)) and 'file' not in kwargs:
		kwargs['file'] = logfile

	# Log to a file output unless specifically told to suppress this feature.
	# (level has no effect on the log file, everything will be written there)
	if 'file' in kwargs and ('suppress' not in kwargs or kwargs['suppress'] == False):
		if type(kwargs['file']) is str:
			with open(kwargs['file'], 'a') as log_file:
				log_file.write(f"{orig_string}\n")
		elif kwargs['file']:
			kwargs['file'].write(f"{orig_string}\n")

	# If we assigned a level, try to log it to systemd's journald.
	# Unless the level is higher than we've decided to output interactively.
	# (Remember, log files still get *ALL* the output despite level restrictions)
	if 'level' in kwargs:
		if 'LOG_LEVEL' not in storage:
			storage['LOG_LEVEL'] = LOG_LEVELS.Info

		if kwargs['level'] > storage['LOG_LEVEL']:
			# Level on log message was Debug, but output level is set to Info.
			# In that case, we'll drop it.
			return None

		try:
			journald.log(string, level=kwargs['level'])
		except ModuleNotFoundError:
			pass # Ignore writing to journald

	# Finally, print the log unless we skipped it based on level.
	# And we print the string which may or may not contain color formatting.
	print(string)