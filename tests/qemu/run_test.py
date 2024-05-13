import time
import asyncio
import threading
import pathlib
import socket
import select
import os
import json
import logging
import sys
from subprocess import Popen, PIPE, STDOUT
from qemu.qmp import QMPClient, Message
from machines import parameters

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
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
				print(f"Event: {event['event']}")
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
	def __init__(self, profile, QMP, serial_socket_path):
		self.profile = profile
		self.QMP = QMP
		self.serial_socket_path = serial_socket_path

		threading.Thread.__init__(self)
		self.start()

	async def edit_boot(self):
		logger.info("Sending 'e'")

		# https://github.com/coreos/qemu/blob/master/qmp-commands.hx
		await self.QMP.qmp.execute_msg(
			self.QMP.qmp.make_execute_msg(
				'send-key',
				arguments={
					'keys': [
						{ "type": "qcode", "data": "e" }
					]
				}
			)
		)

		logger.info("Sending 'end'")
		asyncio.sleep(1)
		ret = await self.QMP.qmp.execute_msg(
			self.QMP.qmp.make_execute_msg(
				'send-key',
				arguments={
					'keys': [
						{ "type": "qcode", "data": "end" }
					]
				}
			)
		)
		asyncio.sleep(1)

		keys = []
		# https://gist.github.com/mvidner/8939289
		keys.append({ "type": "qcode", "data": "spc" })
		for character in list('console=tty0 console=ttyS0,115200'):
			if character.isupper():
				keys.append({ "type": "qcode", "data": 'caps_lock' })
			keys.append({ "type": "qcode", "data": character.lower().replace('=', 'equal').replace(',', 'comma').replace(' ', 'spc') })
			if character.isupper():
				keys.append({ "type": "qcode", "data": 'caps_lock' })
		# keys.append({ "type": "qcode", "data": "kp_enter" })

		ret = await self.QMP.qmp.execute_msg(
			self.QMP.qmp.make_execute_msg(
				'send-key',
				arguments={
					'keys': keys
				}
			)
		)

		await asyncio.sleep(1)
		ret = await self.QMP.qmp.execute_msg(
			self.QMP.qmp.make_execute_msg(
				'send-key',
				arguments={
					'keys': [
						{ "type": "qcode", "data": "kp_enter" }
					]
				}
			)
		)

	async def login_root(self):
		keys = []
		for character in list('root'):
			if character.isupper():
				keys.append({ "type": "qcode", "data": 'caps_lock' })
			keys.append({ "type": "qcode", "data": character.lower().replace('=', 'equal').replace(',', 'comma').replace(' ', 'spc') })
			if character.isupper():
				keys.append({ "type": "qcode", "data": 'caps_lock' })

		ret = await self.QMP.qmp.execute_msg(
			self.QMP.qmp.make_execute_msg(
				'send-key',
				arguments={
					'keys': keys
				}
			)
		)

		await asyncio.sleep(1)
		ret = await self.QMP.qmp.execute_msg(
			self.QMP.qmp.make_execute_msg(
				'send-key',
				arguments={
					'keys': [
						{ "type": "qcode", "data": "kp_enter" }
					]
				}
			)
		)

		await asyncio.sleep(1)
		ret = await self.QMP.qmp.execute_msg(
			self.QMP.qmp.make_execute_msg(
				'send-key',
				arguments={
					'keys': [
						{ "type": "qcode", "data": "kp_enter" }
					]
				}
			)
		)

	def run(self):
		client_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
		client_socket.connect(str(self.serial_socket_path))

		alive = True
		with open('serial.log', 'wb') as fh:
			while alive:
				r, w, x = select.select([client_socket], [], [], 0.2)
				for fd in r:
					if (output := client_socket.recv(8192)):
						if b'Boot in' in output:
							logger.info("Found booting")
							asyncio.run_coroutine_threadsafe(self.edit_boot(), loop=self.QMP.loop)
						elif b'archiso login:' in output:
							logger.info("Found login prompt")
							asyncio.run_coroutine_threadsafe(self.login_root(), loop=self.QMP.loop)

						fh.write(output)
						fh.flush()

					else:
						client_socket.close()
						alive = False
						break
				time.sleep(0.025)

class QemuSession(threading.Thread):
	def __init__(self, cmd, qmp_socket, serial_socket):
		self.cmd = cmd
		self.qmp_socket = qmp_socket
		self.serial_socket = serial_socket

		threading.Thread.__init__(self)
		self.start()

	def run(self):
		#print(self.cmd)
		self.handle = Popen(
			' '.join(self.cmd),
			stdout=PIPE,
			stderr=STDOUT,
			stdin=PIPE,
			shell=True,
			cwd=str(pathlib.Path(__file__).parent),
			pass_fds=[self.qmp_socket.fileno(), self.serial_socket.fileno()]
		)

		while self.handle.poll() is None:
			r, w, x = select.select([self.handle.stdout.fileno(), self.handle.stdout.fileno()], [], [], 0.2)
			for fd in r:
				if fd == self.handle.stdout.fileno():
					if (output := self.handle.stdout.read()):
						print(output)
				#elif fd == self.handle.stderr.fileno():
				#	if (output := self.handle.stderr.read()):
				#		print(output)
			# No exit signal yet
			time.sleep(0.25)

		r, w, x = select.select([self.handle.stdout.fileno(), self.handle.stdout.fileno()], [], [], 0.2)
		for fd in r:
			if fd == self.handle.stdout.fileno():
				if (output := self.handle.stdout.read()):
						print(output)
				#elif fd == self.handle.stderr.fileno():
				#	if (output := self.handle.stderr.read()):
				#		print(output)

		self.handle.stdin.close()
		self.handle.stdout.close()
		# self.handle.stderr.close()
		logger.warning("Qemu closed..")

for profile in parameters:
	qmp_socket_path = pathlib.Path(__file__).parent / "qmp.socket"
	serial_socket_path = pathlib.Path(__file__).parent / "serial.socket"

	qmp_socket_path.unlink(missing_ok=True)
	serial_socket_path.unlink(missing_ok=True)

	with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as qmp_socket:
		with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as serial_socket:
			qmp_socket.bind(str(qmp_socket_path))
			serial_socket.bind(str(serial_socket_path))
			qmp_socket.listen(2)
			serial_socket.listen(2)
			
			args = parameters[profile] + [
				'-chardev', f'socket,id=qmp1,fd={qmp_socket.fileno()},server=on,wait=off',
				'-chardev', f'socket,id=serial1,fd={serial_socket.fileno()},server=on,wait=on',
				'-mon', f'chardev=qmp1,mode=control,pretty=off',
				'-serial', f"chardev:serial1",
				'-drive', f'file=/home/anton/Downloads/archlinux-2024.05.11-x86_64.iso,media=cdrom,cache=none,id=cdrom0,index=0'
			]

			session = QemuSession(args, qmp_socket, serial_socket)
			monitor = QMPClientMonitor(profile, str(qmp_socket_path))
			serial = SerialMonitor(profile, monitor, serial_socket_path)

			asyncio.run(monitor.run())