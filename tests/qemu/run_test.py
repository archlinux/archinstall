import time
import asyncio
import threading
import pathlib
import socket
import select
import logging
import sys
from subprocess import Popen, PIPE, STDOUT
from qemu.qmp import QMPClient
from machines import parameters

logger = logging.getLogger("archtest")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
logger.addHandler(handler)

class QMPClientMonitor:
	def __init__(self, name: str, qmp_socket):
		self.qmp = QMPClient(name)
		self.qmp.logger = logger
		self.qmp_socket = qmp_socket
		self.loop = None

	async def watch_events(self):
		try:
			async for event in self.qmp.events:
				print(f"QMP Event: {event['event']}")
		except asyncio.CancelledError:
			return

	async def run(self):
		self.loop = asyncio.get_event_loop()
		await self.qmp.connect(self.qmp_socket)

		asyncio.create_task(self.watch_events())

		await self.qmp.runstate_changed()
		try:
			await self.qmp.disconnect()
		except:
			pass

class SerialMonitor(threading.Thread):
	def __init__(self, profile, QMP, serial_socket_path, test_case):
		self.profile = profile
		self.QMP = QMP
		self.serial_socket_path = serial_socket_path
		self.test_case = test_case(serial_monitor=self)

		threading.Thread.__init__(self)
		self.start()

	async def edit_boot(self):
		logger.info("Adding 'console=tty0 console=ttyS0,115200' to default boot option")

		# https://github.com/coreos/qemu/blob/master/qmp-commands.hx
		await self.QMP.qmp.execute_msg(
			self.QMP.qmp.make_execute_msg(
				'send-key',
				arguments={
					'keys': [
						{
							"type": "qcode",
							"data": "e"
						}
					]
				}
			)
		)

		await asyncio.sleep(1)
		await self.QMP.qmp.execute_msg(
			self.QMP.qmp.make_execute_msg(
				'send-key',
				arguments={
					'keys': [
						{
							"type": "qcode",
							"data": "end"
						}
					]
				}
			)
		)
		await asyncio.sleep(1)

		keys = []
		# https://gist.github.com/mvidner/8939289
		keys.append({"type": "qcode", "data": "spc"})
		for character in list('console=tty0 console=ttyS0,115200'):
			if character.isupper():
				keys.append({"type": "qcode", "data": 'caps_lock'})
			keys.append({"type": "qcode", "data": character.lower().replace('=', 'equal').replace(',', 'comma').replace(' ', 'spc')})
			if character.isupper():
				keys.append({"type": "qcode", "data": 'caps_lock'})

		await self.QMP.qmp.execute_msg(
			self.QMP.qmp.make_execute_msg(
				'send-key',
				arguments={
					'keys': keys
				}
			)
		)

		await asyncio.sleep(1)
		await self.QMP.qmp.execute_msg(
			self.QMP.qmp.make_execute_msg(
				'send-key',
				arguments={
					'keys': [
						{
							"type": "qcode",
							"data": "kp_enter"
						}
					]
				}
			)
		)

	async def login_root(self):
		self.client_socket.send(b'root\015')

	async def run_archinstall(self):
		# self.client_socket.send(b'tput cols\015')
		# self.client_socket.send(b'tput lines\015')

		# For some reason, while running in this test mode,
		# building archinstall fails randomly with "No such file or directory"."
		# So a safe bet is to just re-run it manually before starting.
		self.client_socket.send(b'python -m build --verbose --wheel --no-isolation\015')
		time.sleep(1)
		self.client_socket.send(b'pip install dist/archinstall*.whl --break-system-packages\015')
		time.sleep(1)
		self.client_socket.send(b'archinstall\015')

	def run(self):
		self.client_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
		self.client_socket.connect(str(self.serial_socket_path))

		alive = True
		entered_test_case = False
		# The output of serial.log can be displayed with:
		#   tail -f serial.log
		# Or record with:
		#   asciinema rec demo.cast -c "tail -f serial.log"
		with open('serial.log', 'wb') as fh:
			while alive and self.test_case.exit_code == -1:
				r, w, x = select.select([self.client_socket], [], [], 0.2)
				for fd in r:
					if (output := self.client_socket.recv(8192)):
						fh.write(output)
						fh.flush()

						# This block should be moved into the test class
						if b'Boot in' in output and entered_test_case is False:
							logger.info("Found boot prompt")
							asyncio.run_coroutine_threadsafe(self.edit_boot(), loop=self.QMP.loop)
						elif b'archiso login:' in output and entered_test_case is False:
							logger.info("Found login prompt")
							asyncio.run_coroutine_threadsafe(self.login_root(), loop=self.QMP.loop)
						elif b'Type archinstall to launch the installer.' in output and entered_test_case is False:
							logger.info("Found archinstall start point")
							asyncio.run_coroutine_threadsafe(self.run_archinstall(), loop=self.QMP.loop)
							entered_test_case = True
						# -------
						elif entered_test_case:
							self.test_case.feed(output)

					else:
						self.client_socket.close()
						alive = False
						break
				time.sleep(0.025)

		print(f"Serial died: {alive}, {self.test_case.exit_code}")

class QemuSession(threading.Thread):
	def __init__(self, cmd, qmp_socket, serial_socket):
		self.cmd = cmd
		self.qmp_socket = qmp_socket
		self.serial_socket = serial_socket

		threading.Thread.__init__(self)
		self.start()

	def run(self):
		self.handle = Popen(
			' '.join(self.cmd),
			stdout=PIPE,
			stderr=STDOUT,
			stdin=PIPE,
			shell=True,
			cwd=str(pathlib.Path(__file__).parent),
			pass_fds=[self.qmp_socket.fileno(), self.serial_socket.fileno()]
		)

		# Run the qemu process until complete.
		# And deal with the different buffers accordingly
		while self.handle.poll() is None:
			r, w, x = select.select([self.handle.stdout.fileno(), self.handle.stdout.fileno()], [], [], 0.2)
			for fd in r:
				if fd == self.handle.stdout.fileno():
					if (output := self.handle.stdout.read()):
						print(output)
				# elif fd == self.handle.stderr.fileno():
				# 	if (output := self.handle.stderr.read()):
				# 		print(output)
			# No exit signal yet
			time.sleep(0.25)

		r, w, x = select.select([self.handle.stdout.fileno(), self.handle.stdout.fileno()], [], [], 0.2)
		for fd in r:
			if fd == self.handle.stdout.fileno():
				if (output := self.handle.stdout.read()):
					print(output)
				# elif fd == self.handle.stderr.fileno():
				# 	if (output := self.handle.stderr.read()):
				# 		print(output)

		self.handle.stdin.close()
		self.handle.stdout.close()
		# self.handle.stderr.close()
		logger.warning("Qemu closed..")


# .. todo::
#    Needs a bit of more work to allow for multiple runners and test benches.
for profile in parameters:
	qmp_socket_path = pathlib.Path(__file__).parent / "qmp.socket"
	serial_socket_path = pathlib.Path(__file__).parent / "serial.socket"

	qmp_socket_path.unlink(missing_ok=True)
	serial_socket_path.unlink(missing_ok=True)

	logger.info(f"Creating serial ttyS0 and QMP sockets for use in Qemu")
	with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as qmp_socket:
		with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as serial_socket:
			qmp_socket.bind(str(qmp_socket_path))
			serial_socket.bind(str(serial_socket_path))
			qmp_socket.listen(2)
			serial_socket.listen(2)
			
			args = parameters[profile]['arguments'] + [
				'-chardev', f'socket,id=qmp1,fd={qmp_socket.fileno()},server=on,wait=off',
				'-chardev', f'socket,id=serial1,fd={serial_socket.fileno()},server=on,wait=on',
				'-mon', f'chardev=qmp1,mode=control,pretty=off',
				'-serial', f"chardev:serial1",
				'-drive', f'file=$(ls -t ./_work/iso/archlinux-*-x86_64.iso | head -n 1),media=cdrom,cache=none,id=cdrom0,index=0'
			]

			logger.info(f"Spawning Qemu test profile {profile}")
			session = QemuSession(args, qmp_socket, serial_socket)
			monitor = QMPClientMonitor(profile, str(qmp_socket_path))
			serial = SerialMonitor(profile, monitor, serial_socket_path, test_case=parameters[profile]['test_class'])

			asyncio.run(monitor.run())