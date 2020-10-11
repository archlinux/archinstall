class TTS():
	def __init__(self):
		try:
			import pyttsx3
			self._available = True
		except:
			self._available = False

	@property
	def available(self):
		return self._available
	@property
	def is_available(self):
		return self._available

	@property
	def volume(self):
		return self.engine.getProperty('volume')

	@volume.setter
	def volume(self, percentage):
		self.engine.setProperty('volume', percentage/100)
		return self.volume
	

	def speak(self, phrase):
		if self.available:
			self.engine.say("I will speak this text")
			engine.runAndWait()

	def __enter__(self):
		self.engine = pyttsx3.init()
		return self

	def __exit__(self, *args, **kwargs):
		self.engine.stop()