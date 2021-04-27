import abc
import os
import sys
import logging
from pathlib import Path
from .storage import storage

# TODO: use logging's built in levels instead.
#       Although logging is threaded and I wish to avoid that.
#       It's more Pythonistic or w/e you want to call it.
class LOG_LEVELS:
	Critical = 0b001
	Error = 0b010
	Warning = 0b011
	Info = 0b101
	Debug = 0b111

class journald(dict):
	@abc.abstractmethod
	def log(message, level=logging.DEBUG):
		try:
			import systemd.journal
		except ModuleNotFoundError:
			return False

		# For backwards compability, convert old style log-levels
		# to logging levels (and warn about deprecated usage)
		# There's some code re-usage here but that should be fine.
		# TODO: Remove these in a few versions:
		if level == LOG_LEVELS.Critical:
			log("Deprecated level detected in log message, please use new logging.<level> instead for the following log message:", fg="red", level=logging.ERROR, force=True)
			level = logging.CRITICAL
		elif level == LOG_LEVELS.Error:
			log("Deprecated level detected in log message, please use new logging.<level> instead for the following log message:", fg="red", level=logging.ERROR, force=True)
			level = logging.ERROR
		elif level == LOG_LEVELS.Warning:
			log("Deprecated level detected in log message, please use new logging.<level> instead for the following log message:", fg="red", level=logging.ERROR, force=True)
			level = logging.WARNING
		elif level == LOG_LEVELS.Info:
			log("Deprecated level detected in log message, please use new logging.<level> instead for the following log message:", fg="red", level=logging.ERROR, force=True)
			level = logging.INFO
		elif level == LOG_LEVELS.Debug:
			log("Deprecated level detected in log message, please use new logging.<level> instead for the following log message:", fg="red", level=logging.ERROR, force=True)
			level = logging.DEBUG

		log_adapter = logging.getLogger('archinstall')
		log_fmt = logging.Formatter("[%(levelname)s]: %(message)s")
		log_ch = systemd.journal.JournalHandler()
		log_ch.setFormatter(log_fmt)
		log_adapter.addHandler(log_ch)
		log_adapter.setLevel(logging.DEBUG)
		
		log_adapter.log(level, message)

# TODO: Replace log() for session based logging.
class SessionLogging():
	def __init__(self):
		pass

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

	# Attempt to colorize the output if supported
	# Insert default colors and override with **kwargs
	if supports_color():
		kwargs = {'fg': 'white', **kwargs}
		string = stylize_output(string, **kwargs)

	# If a logfile is defined in storage,
	# we use that one to output everything
	if (filename := storage.get('LOG_FILE', None)):
		absolute_logfile = os.path.join(storage.get('LOG_PATH', './'), filename)
		if not os.path.isfile(absolute_logfile):
			try:
				Path(absolute_logfile).parents[0].mkdir(exist_ok=True, parents=True)
			except PermissionError:
				# Fallback to creating the log file in the current folder
				err_string = f"Not enough permission to place log file at {absolute_logfile}, creating it in {Path('./').absolute()/filename} instead."
				absolute_logfile = Path('./').absolute()/filename
				absolute_logfile.parents[0].mkdir(exist_ok=True)
				absolute_logfile = str(absolute_logfile)
				storage['LOG_PATH'] = './'
				log(err_string, fg="red")

			Path(absolute_logfile).touch() # Overkill?

		with open(absolute_logfile, 'a') as log_file:
			log_file.write(f"{orig_string}\n")


	# If we assigned a level, try to log it to systemd's journald.
	# Unless the level is higher than we've decided to output interactively.
	# (Remember, log files still get *ALL* the output despite level restrictions)
	if 'level' in kwargs:
		# For backwards compability, convert old style log-levels
		# to logging levels (and warn about deprecated usage)
		# There's some code re-usage here but that should be fine.
		# TODO: Remove these in a few versions:
		if kwargs['level'] == LOG_LEVELS.Critical:
			log("Deprecated level detected in log message, please use new logging.<level> instead for the following log message:", fg="red", level=logging.ERROR, force=True)
			kwargs['level'] = logging.CRITICAL
		elif kwargs['level'] == LOG_LEVELS.Error:
			log("Deprecated level detected in log message, please use new logging.<level> instead for the following log message:", fg="red", level=logging.ERROR, force=True)
			kwargs['level'] = logging.ERROR
		elif kwargs['level'] == LOG_LEVELS.Warning:
			log("Deprecated level detected in log message, please use new logging.<level> instead for the following log message:", fg="red", level=logging.ERROR, force=True)
			kwargs['level'] = logging.WARNING
		elif kwargs['level'] == LOG_LEVELS.Info:
			log("Deprecated level detected in log message, please use new logging.<level> instead for the following log message:", fg="red", level=logging.ERROR, force=True)
			kwargs['level'] = logging.INFO
		elif kwargs['level'] == LOG_LEVELS.Debug:
			log("Deprecated level detected in log message, please use new logging.<level> instead for the following log message:", fg="red", level=logging.ERROR, force=True)
			kwargs['level'] = logging.DEBUG

		if kwargs['level'] > storage.get('LOG_LEVEL', logging.INFO) and not 'force' in kwargs:
			# Level on log message was Debug, but output level is set to Info.
			# In that case, we'll drop it.
			return None

	try:
		journald.log(string, level=kwargs.get('level', logging.INFO))
	except ModuleNotFoundError:
		pass # Ignore writing to journald

	# Finally, print the log unless we skipped it based on level.
	# We use sys.stdout.write()+flush() instead of print() to try and
	# fix issue #94
	sys.stdout.write(f"{string}\n")
	sys.stdout.flush()
