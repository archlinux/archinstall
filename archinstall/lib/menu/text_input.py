import readline
import sys


class TextInput:
	def __init__(self, prompt: str, prefilled_text=''):
		self._prompt = prompt
		self._prefilled_text = prefilled_text

	def _hook(self):
		readline.insert_text(self._prefilled_text)
		readline.redisplay()

	def run(self) -> str:
		readline.set_pre_input_hook(self._hook)
		try:
			result = input(self._prompt)
		except (KeyboardInterrupt, EOFError):
			# To make sure any output that may follow
			# will be on the line after the prompt
			sys.stdout.write('\n')
			sys.stdout.flush()

			result = ''
		readline.set_pre_input_hook()
		return result
