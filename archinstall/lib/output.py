import sys
from .tts import TTS

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
	string = ' '.join([str(x) for x in args])
	if supports_color():
		kwargs = {'bg' : 'black', 'fg': 'white', **kwargs}
		string = stylize_output(string, **kwargs)

	print(string)
	with TTS() as tts_instance:
		if tts_instance.is_available:
			tts_instance.speak(string.replace('-', '').strip().lstrip())
