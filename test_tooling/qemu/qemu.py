import getpass
import grp
import hashlib
import os
import pathlib
import re
import shlex
import shutil
import subprocess
import sys
import time
from argparse import ArgumentParser
from collections.abc import Iterator
from select import EPOLLHUP, EPOLLIN, epoll
from shutil import which
from types import TracebackType
from typing import Any, Self, override


class RequirementError(Exception):
	pass


class ArgumentError(Exception):
	pass


def get_master(interface):
	master_path = pathlib.Path(f'/sys/class/net/{interface}/master')
	return master_path.readlink().name if master_path.exists() else None


def gray(text):
	return f'\033[38;5;246m{text}\033[0m'


def orange(text):
	return f'\033[38;5;208m{text}\033[0m'


def red(text):
	return f'\033[31m{text}\033[0m'


sudo_password = None  # Gets populated later
harddrives = {}
username = getpass.getuser()
groupname = grp.getgrgid(os.getgid()).gr_name

# https://stackoverflow.com/a/43627833/929999
_VT100_ESCAPE_REGEX = r'\x1B\[[?0-9;]*[a-zA-Z]'
_VT100_ESCAPE_REGEX_BYTES = _VT100_ESCAPE_REGEX.encode()

parser = ArgumentParser(description='A set of common parameters for the tooling', add_help=True)

# Defaults to the order of which the harddrives are defined.
boot_option = parser.add_mutually_exclusive_group()
boot_option.add_argument('--uki', help='Boot a UKI (EFI) image')
boot_option.add_argument('--kernel', help='Boot a Linux kernel')
boot_option.add_argument('--iso', help='Boot a ISO 9660')

networking = parser.add_argument_group('Networking', "Disables the default '-net nic -net user' network behavior of Qemu.")
networking.add_argument('--tap', nargs='?', help='Configures a TAP interface and passes it in as a virtio-net-pci.', default=None, type=str)
networking.add_argument('--tap-mac', nargs='?', help='MAC for the --tap interface', default='52:54:00:00:00:02')
networking.add_argument('--bridge', nargs='?', help='Configures a bridge, to which the --tap is added.', default=None, type=str)
networking.add_argument('--bridge-mac', nargs='?', help='MAC for the interface', default=None)
networking.add_argument('--bridge-master', nargs='?', help="Which interface to set as 'master' on the bridge.", default=None, type=str)

hardware = parser.add_argument_group('Hardware', 'General hardware specs for the virtual machine')
# To override the use of EFI boot (will not work with --uki for obvious reasons)
hardware.add_argument('--bios', action='store_true', help='Disables EFI (edk2/ovmf) and uses BIOS support instead', default=False)
hardware.add_argument('--memory', nargs='?', help='Ammount of memory to supply the machine', default=8192)
hardware.add_argument('--harddrive', action='append', help='Sets up one or more virtio-scsi-pci, size is defined by --harddrive test.qcow2:15G', type=str)
hardware.add_argument('--cpu', help='Sets the number of cores to allocate (default nproc -1)', type=str, default=os.cpu_count() - 1 if os.cpu_count() else 1)
hardware.add_argument('--resolution', help="Sets Qemu's VGA resolution", type=str, default='1920x1107')

kernel = parser.add_argument_group('Kernel', '--kernel specific arguments')
kernel.add_argument('--initrd', nargs='?', help='Defines which ISO to run (skips build all together)', default=None, type=pathlib.Path)

args, unknowns = parser.parse_known_args()  # pylint: disable=redefined-outer-name

if args.bios and args.uki:
	raise ArgumentError('Cannot boot a --uki image with --bios mode (at least not that I know of).')

if args.uki is None and args.kernel is None and args.iso is None and args.harddrive is None:
	raise ArgumentError('Cannot boot this machine, define at least one of: --uki, --kernel, --iso, --harddrive')

if args.bridge is None and args.bridge_master:
	raise ArgumentError('Cannot use --bridge-master without defining --bridge')

if args.bridge is None and args.bridge_mac:
	raise ArgumentError('Cannot use --bridge-mac without defining --bridge')
elif args.bridge and args.bridge_mac is None:
	args.bridge_mac = '52:54:00:00:00:1'

if args.tap and not args.bridge and get_master(args.tap) is None:
	# We'll allow it, because maybe we're tesing what happens without networking, but the NIC exists. Or the user has some creative iptables/nftables forwarding.
	print(orange('--tap does not have a master, consider adding --bridge or manual set a master using ip-link(8).'))

if args.tap is None and args.bridge:
	print(orange("--bridge* arguments will be ignored since there's no --tap defined"))
elif args.tap and args.tap_mac is None:
	args.tap_mac = '52:54:00:00:00:2'


class SysCallError(Exception):
	def __init__(self, message: str, exit_code: int | None = None, worker_log: bytes = b'') -> None:
		super().__init__(message)
		self.message = message
		self.exit_code = exit_code
		self.worker_log = worker_log


def clear_vt100_escape_codes(data: bytes) -> bytes:
	return re.sub(_VT100_ESCAPE_REGEX_BYTES, b'', data)


def locate_binary(name: str) -> str:
	if path := which(name):
		return path
	raise RequirementError(f'Binary {name} does not exist.')


def _pid_exists(pid: int) -> bool:
	try:
		return any(subprocess.check_output(['ps', '--no-headers', '-o', 'pid', '-p', str(pid)]).strip())
	except subprocess.CalledProcessError:
		return False


class SysCommandWorker:
	def __init__(
		self,
		cmd: str | list[str],
		peek_output: bool | None = False,
		environment_vars: dict[str, str] | None = None,
		working_directory: str = './',
		remove_vt100_escape_codes_from_lines: bool = True,
	):
		if isinstance(cmd, str):
			cmd = shlex.split(cmd)

		if cmd and not cmd[0].startswith(('/', './')):  # Path() does not work well
			cmd[0] = locate_binary(cmd[0])

		self.cmd = cmd
		self.peek_output = peek_output
		# define the standard locale for command outputs. For now the C ascii one. Can be overridden
		self.environment_vars = {'LC_ALL': 'C'}
		if environment_vars:
			self.environment_vars.update(environment_vars)

		self.working_directory = working_directory

		self.exit_code: int | None = None
		self._trace_log = b''
		self._trace_log_pos = 0
		self.poll_object = epoll()
		self.child_fd: int | None = None
		self.started = False
		self.ended = False
		self.remove_vt100_escape_codes_from_lines: bool = remove_vt100_escape_codes_from_lines

	def __contains__(self, key: bytes) -> bool:
		"""
		Contains will also move the current buffert position forward.
		This is to avoid re-checking the same data when looking for output.
		"""
		assert isinstance(key, bytes)

		index = self._trace_log.find(key, self._trace_log_pos)
		if index >= 0:
			self._trace_log_pos += index + len(key)
			return True

		return False

	def __iter__(self, *args: str, **kwargs: dict[str, Any]) -> Iterator[bytes]:  # pylint: disable=redefined-outer-name
		last_line = self._trace_log.rfind(b'\n')
		lines = filter(None, self._trace_log[self._trace_log_pos : last_line].splitlines())
		for line in lines:
			if self.remove_vt100_escape_codes_from_lines:
				line = clear_vt100_escape_codes(line)

			yield line + b'\n'

		self._trace_log_pos = last_line

	@override
	def __repr__(self) -> str:
		self.make_sure_we_are_executing()
		return str(self._trace_log)

	@override
	def __str__(self) -> str:
		try:
			return self._trace_log.decode('utf-8')
		except UnicodeDecodeError:
			return str(self._trace_log)

	def __enter__(self) -> Self:
		return self

	def __exit__(self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None) -> None:
		# b''.join(sys_command('sync')) # No need to, since the underlying fs() object will call sync.
		# TODO: https://stackoverflow.com/questions/28157929/how-to-safely-handle-an-exception-inside-a-context-manager

		if self.child_fd:
			try:
				os.close(self.child_fd)
			except Exception:
				pass

		if self.peek_output:
			# To make sure any peaked output didn't leave us hanging
			# on the same line we were on.
			sys.stdout.write('\n')
			sys.stdout.flush()

		if exc_type is not None:
			print(gray(str(exc_value)))

		if self.exit_code != 0:
			raise SysCallError(
				f'{self.cmd} exited with abnormal exit code [{self.exit_code}]: {str(self)[-500:]}',
				self.exit_code,
				worker_log=self._trace_log,
			)

	def is_alive(self) -> bool:
		self.poll()

		if self.started and not self.ended:
			return True

		return False

	def write(self, data: bytes, line_ending: bool = True) -> int:
		assert isinstance(data, bytes)  # TODO: Maybe we can support str as well and encode it

		self.make_sure_we_are_executing()

		if self.child_fd:
			return os.write(self.child_fd, data + (b'\n' if line_ending else b''))

		return 0

	def make_sure_we_are_executing(self) -> bool:
		if not self.started:
			return self.execute()
		return True

	def tell(self) -> int:
		self.make_sure_we_are_executing()
		return self._trace_log_pos

	def seek(self, pos: int) -> None:
		self.make_sure_we_are_executing()
		# Safety check to ensure 0 < pos < len(tracelog)
		self._trace_log_pos = min(max(0, pos), len(self._trace_log))

	def peak(self, output: str | bytes) -> bool:
		if self.peek_output:
			if isinstance(output, bytes):
				try:
					output = output.decode('UTF-8')
				except UnicodeDecodeError:
					return False

			sys.stdout.write(output)
			sys.stdout.flush()

		return True

	def poll(self) -> None:
		self.make_sure_we_are_executing()

		if self.child_fd:
			got_output = False
			for _fileno, _event in self.poll_object.poll(0.1):
				try:
					output = os.read(self.child_fd, 8192)
					got_output = True
					self.peak(output)
					self._trace_log += output
				except OSError:
					self.ended = True
					break

			if self.ended or (not got_output and not _pid_exists(self.pid)):
				self.ended = True
				try:
					wait_status = os.waitpid(self.pid, 0)[1]
					self.exit_code = os.waitstatus_to_exitcode(wait_status)
				except ChildProcessError:
					try:
						wait_status = os.waitpid(self.child_fd, 0)[1]
						self.exit_code = os.waitstatus_to_exitcode(wait_status)
					except ChildProcessError:
						self.exit_code = 1

	def execute(self) -> bool:
		import pty

		if (old_dir := os.getcwd()) != self.working_directory:
			os.chdir(str(self.working_directory))

		# Note: If for any reason, we get a Python exception between here
		# and until os.close(), the traceback will get locked inside
		# stdout of the child_fd object. `os.read(self.child_fd, 8192)` is the
		# only way to get the traceback without losing it.

		self.pid, self.child_fd = pty.fork()

		# https://stackoverflow.com/questions/4022600/python-pty-fork-how-does-it-work
		if not self.pid:
			try:
				os.execve(self.cmd[0], list(self.cmd), {**os.environ, **self.environment_vars})
			except FileNotFoundError:
				print(red(f'{self.cmd[0]} does not exist.'))
				self.exit_code = 1
				return False
		else:
			# Only parent process moves back to the original working directory
			os.chdir(old_dir)

		self.started = True
		self.poll_object.register(self.child_fd, EPOLLIN | EPOLLHUP)

		return True

	def decode(self, encoding: str = 'UTF-8') -> str:
		return self._trace_log.decode(encoding)


def ensure_sudo():
	global sudo_password  # pylint: disable=global-statement

	if sudo_password is None:
		if (sudo_password := getpass.getpass(f'[sudo] password for {username}: ')) == '':
			raise ValueError('Certain commands need sudo to work and no sudo password was given.')


def setup_networking():
	if args.tap:
		if pathlib.Path(f'/sys/class/net/{args.tap}').exists() is False:
			print(gray(f'Creating {args.tap} for user {username} and group {groupname}'))
			handle, pw_prompted = SysCommandWorker(f'sudo ip tuntap add dev {args.tap} mode tap user {username} group {groupname}'), False
			while handle.is_alive():
				if b'password for' in handle and pw_prompted is False:
					ensure_sudo()
					handle.write(bytes(sudo_password, 'UTF-8'))
					pw_prompted = True

		if args.bridge:
			if pathlib.Path(f'/sys/class/net/{args.bridge}').exists() is False:
				print(gray(f'Creating {args.bridge}'))
				handle, pw_prompted = SysCommandWorker(f'sudo ip link add name {args.bridge} type bridge'), False
				while handle.is_alive():
					if b'password for' in handle and pw_prompted is False:
						ensure_sudo()
						handle.write(bytes(sudo_password, 'UTF-8'))
						pw_prompted = True

			if args.bridge_mac:
				handle, pw_prompted = SysCommandWorker(f'sudo ip link set dev {args.bridge} address {args.bridge_mac}'), False
				print(gray(f'Setting bridge {args.bridge} MAC address to {args.bridge_mac}'))
				while handle.is_alive():
					if b'password for' in handle and pw_prompted is False:
						ensure_sudo()
						handle.write(bytes(sudo_password, 'UTF-8'))
						pw_prompted = True

			if args.bridge_master and get_master(args.bridge) != args.bridge_master:
				handle, pw_prompted = SysCommandWorker(f'sudo ip link set dev {args.bridge_master} master {args.bridge}'), False
				print(gray(f'Setting interface {args.bridge_master} master to {args.bridge}'))
				while handle.is_alive():
					if b'password for' in handle and pw_prompted is False:
						ensure_sudo()
						handle.write(bytes(sudo_password, 'UTF-8'))
						pw_prompted = True

			print(gray(f'Setting interface {args.tap} master to {args.bridge}'))
			handle, pw_prompted = SysCommandWorker(f'sudo ip link set dev {args.tap} master {args.bridge}'), False
			while handle.is_alive():
				if b'password for' in handle and pw_prompted is False:
					ensure_sudo()
					handle.write(bytes(sudo_password, 'UTF-8'))
					pw_prompted = True

			print(gray(f'Bringing up bridge {args.bridge}'))
			handle, pw_prompted = SysCommandWorker(f'sudo ip link set dev {args.bridge} up'), False
			while handle.is_alive():
				if b'password for' in handle and pw_prompted is False:
					ensure_sudo()
					handle.write(bytes(sudo_password, 'UTF-8'))
					pw_prompted = True

		print(gray(f'Bringing interface {args.tap} up'))
		handle, pw_prompted = SysCommandWorker(f'sudo ip link set dev {args.tap} up'), False
		while handle.is_alive():
			if b'password for' in handle and pw_prompted is False:
				ensure_sudo()
				handle.write(bytes(sudo_password, 'UTF-8'))
				pw_prompted = True


def setup_disks():
	if args.harddrive:
		for harddrive_arg in args.harddrive:
			path, size = harddrive_arg.split(':')
			path = pathlib.Path(path.strip()).expanduser().resolve().absolute()
			harddrives[path] = size.strip()

			if path.exists() is False:
				handle = SysCommandWorker(f'qemu-img create -f qcow2 {hdd} {size}')
				while handle.is_alive():
					time.sleep(0.01)

				if handle.exit_code != 0:
					raise ValueError(f'Could not create harddrive {hdd}: {handle}')


setup_networking()
setup_disks()

if args.uki or args.bios is False:
	disk_paths_hash = hashlib.sha1((''.join(sorted([str(x) for x in harddrives.keys()]))).encode()).hexdigest()

	shutil.copy2('/usr/share/ovmf/x64/OVMF_CODE.secboot.4m.fd', f'./OVMF_CODE.secboot.4m.fd.{disk_paths_hash}')
	shutil.copy2('/usr/share/ovmf/x64/OVMF_VARS.4m.fd', f'./OVMF_VARS.4m.fd.{disk_paths_hash}')

boot_index = 0
qemu = 'qemu-system-x86_64'
qemu += ' -cpu host'
qemu += ' -enable-kvm'
qemu += ' -machine q35,accel=kvm'
qemu += ' -object rng-random,filename=/dev/urandom,id=rng0'
qemu += ' -device virtio-rng-pci,rng=rng0'
qemu += ' -global driver=cfi.pflash01,property=secure,value=on'
qemu += f' -smp {args.cpu},sockets=1,dies=1,cores={args.cpu},threads=1'
# qemu += f' -vga vga'
qemu += f' -device VGA,edid=on,xres={args.resolution.split("x")[0]},yres={args.resolution.split("x")[1]}'
qemu += ' -device intel-iommu,device-iotlb=on,caching-mode=on'
qemu += f' -m {args.memory}'
if args.bios is False:
	qemu += f' -drive if=pflash,format=raw,readonly=on,file=./OVMF_CODE.secboot.4m.fd.{disk_paths_hash}'
	qemu += f' -drive if=pflash,format=raw,file=./OVMF_VARS.4m.fd.{disk_paths_hash}'
if args.uki:
	qemu += f' -kernel {args.uki}'
	boot_index += 1
scsi_index = 0
for scsi_index, hdd in enumerate(harddrives.keys()):
	# qemu += f' -device virtio-scsi-pci,bus=pcie.0,id=scsi{index}'
	# qemu += f'  -device scsi-hd,drive=hdd{index},bus=scsi{index}.0,id=scsi{index}.0,bootindex={hdd_boot_priority+index}'
	# qemu += f'   -drive file={hdd},if=none,format=qcow2,discard=unmap,aio=native,cache=none,id=hdd{index}'
	qemu += f' -device virtio-scsi-pci,bus=pcie.0,id=scsi{scsi_index},addr=0x{scsi_index + 8}'
	qemu += f'  -device scsi-hd,drive=libvirt-{scsi_index}-format,bus=scsi{scsi_index}.0,id=scsi{scsi_index}-0-0-0,channel=0,scsi-id=0,lun=0,device_id=drive-scsi0-0-0-0,bootindex={boot_index},write-cache=on'
	qemu += f'   -blockdev \'{{"driver":"file","filename":"{hdd}","aio":"threads","node-name":"libvirt-{scsi_index}-storage","cache":{{"direct":false,"no-flush":false}},"auto-read-only":true,"discard":"unmap"}}\''
	qemu += f'   -blockdev \'{{"node-name":"libvirt-{scsi_index}-format","read-only":false,"discard":"unmap","cache":{{"direct":true,"no-flush":false}},"driver":"qcow2","file":"libvirt-{scsi_index}-storage","backing":null}}\''
	boot_index += 1
if args.iso:
	qemu += f' -device virtio-scsi-pci,bus=pcie.0,id=scsi{scsi_index + 1}'
	qemu += f'  -device scsi-cd,drive=cdrom0,bus=scsi{scsi_index + 1}.0,bootindex={boot_index}'
	qemu += f'   -drive file={args.iso},media=cdrom,if=none,format=raw,cache=none,id=cdrom0'
	boot_index += 1

# if args.vfio:
# 	qemu += f'  -drive file={args.vfio},index=2,media=cdrom'

if args.tap:
	qemu += f'  -device virtio-net-pci,mac={args.tap_mac},id=network0,netdev=network0.0,status=on,bus=pcie.0'
	qemu += f'   -netdev tap,ifname={args.tap},id=network0.0,script=no,downscript=no'

print(gray(qemu))

qemu_session = subprocess.run(shlex.split(qemu), check=True, capture_output=True)

if qemu_session.stdout:
	print(qemu_session.stdout.decode())
if qemu_session.returncode != 0:
	print(red(qemu_session.stderr.decode()))
