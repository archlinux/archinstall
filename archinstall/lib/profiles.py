from __future__ import annotations

import importlib.util
import os
import sys
from types import ModuleType
from typing import Optional, TYPE_CHECKING, Any

# https://stackoverflow.com/a/39757388/929999
if TYPE_CHECKING:
	from .installer import Installer
	_: Any


class Script:
	def __init__(self, profile :str, installer :Optional[Installer] = None):
		"""
		:param profile: A string representing either a boundled profile, a local python file
			or a remote path (URL) to a python script-profile. Three examples:
			* profile: https://archlinux.org/some_profile.py
			* profile: desktop
			* profile: /path/to/profile.py
		"""
		self.profile = profile
		self.installer = installer # TODO: Appears not to be used anymore?
		self.converted_path = None
		self.spec = None
		self.examples = {}
		self.namespace = os.path.splitext(os.path.basename(self.path))[0]
		self.original_namespace = self.namespace

	def __enter__(self, *args :str, **kwargs :str) -> ModuleType:
		self.execute()
		return sys.modules[self.namespace]

	def __exit__(self, *args :str, **kwargs :str) -> None:
		# TODO: https://stackoverflow.com/questions/28157929/how-to-safely-handle-an-exception-inside-a-context-manager
		if len(args) >= 2 and args[1]:
			raise args[1]

		if self.original_namespace:
			self.namespace = self.original_namespace

	def load_instructions(self, namespace :Optional[str] = None) -> 'Script':
		if namespace:
			self.namespace = namespace

		self.spec = importlib.util.spec_from_file_location(self.namespace, self.path)
		imported = importlib.util.module_from_spec(self.spec)
		sys.modules[self.namespace] = imported

		return self

	def execute(self) -> ModuleType:
		if self.namespace not in sys.modules or self.spec is None:
			self.load_instructions()

		self.spec.loader.exec_module(sys.modules[self.namespace])

		return sys.modules[self.namespace]
