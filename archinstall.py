import os, stat

from exceptions import *
from helpers.disk import *
from helpers.general import *
from helpers.user_interaction import *

class HardDrive():
	def __init__(self, full_path:str, *args, **kwargs):
		if not stat.S_ISBLK(os.stat(full_path).st_mode):
			raise DiskError(f'Selected disk "{full_path}" is not a block device.')

class installer():
	def __init__(self, partition, *, profile=None, hostname='ArchInstalled'):
		self.profile = profile
		self.hostname = hostname

		self.partition = partition

	def minimal_installation(self):
		pass