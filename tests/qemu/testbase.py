import enum
import time
import threading
import select
import logging
import socket

logger = logging.getLogger("archtest")

class Keyboard(enum.Enum):
	# https://vt100.net/docs/vt100-ug/chapter3.html
	# https://espterm.github.io/docs/VT100%20escape%20codes.html
	arrow_up = '\033[A'
	arrow_down = '\033[B'
	arrow_right = '\033[C'
	arrow_left = '\033[D'
	enter = '\015'
	forward_slash = '\057'
	escape = '\033'

class TestBase(threading.Thread):
	def __init__(self, serial_monitor):
		self.serial_monitor = serial_monitor
		self.buffer = b''

	async def _send_key(self, key):
		pass # This is for the QMP socket if needed

	def send_string(self, chars, delay=None):
		logger.debug(f"Sending string: {chars.encode('UTF-8')}")

		while len(select.select([self.serial_monitor.client_socket], [], [], 0.2)[0]):
			# Waiting for read buffer to finish to not collide
			time.sleep(0.02)

		if len(select.select([], [self.serial_monitor.client_socket], [], 0.2)[1]):
			# asyncio.run_coroutine_threadsafe(self._send_key(vt100_key), loop=self.serial_monitor.QMP.loop)
			self.serial_monitor.client_socket.send(chars.encode('UTF-8'), socket.MSG_WAITALL) # flags=socket.MSG_WAITALL
			# os.fsync(self.serial_monitor.client_socket.fileno())
		else:
			logger.error(f"Could not send key, serial was not in a write state!")

		if delay:
			time.sleep(delay)

	def send_key(self, key, delay=None):
		try:
			vt100_key = Keyboard[key].value.encode('UTF-8')
		except:
			# logger.warning(f"Could not convert key: {key}")
			vt100_key = key.encode('UTF-8')

		logger.debug(f"Sending key: {key} \033[0;32m({vt100_key})\033[0m")

		while len(select.select([self.serial_monitor.client_socket], [], [], 0.2)[0]):
			# Waiting for read buffer to finish to not collide
			time.sleep(0.02)

		if len(select.select([], [self.serial_monitor.client_socket], [], 0.2)[1]):
			# asyncio.run_coroutine_threadsafe(self._send_key(vt100_key), loop=self.serial_monitor.QMP.loop)
			self.serial_monitor.client_socket.send(vt100_key, socket.MSG_WAITALL) # flags=socket.MSG_WAITALL
			# os.fsync(self.serial_monitor.client_socket.fileno())
		else:
			logger.error(f"Could not send key, serial was not in a write state!")

		if delay:
			time.sleep(delay)

		# Flushing the serial buffer, as it can quickly become frozen
		# self.serial_monitor.client_socket.sendall(b"")

	def feed(self, line):
		self.buffer += line