import readline


class TextInput:
	def __init__(self, prompt: str, prefilled_text=''):
		self._prompt = prompt
		self._prefilled_text = prefilled_text

	def _hook(self):
		readline.insert_text(self._prefilled_text)
		readline.redisplay()

	def run(self) -> str:
		readline.set_pre_input_hook(self._hook)
		result = input(self._prompt)
		readline.set_pre_input_hook()
		return result
