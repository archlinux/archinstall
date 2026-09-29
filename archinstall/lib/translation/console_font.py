import os
import tempfile
from pathlib import Path

from archinstall.lib.command import SysCommand
from archinstall.lib.exceptions import SysCallError
from archinstall.lib.log import debug
from archinstall.lib.utils.util import running_from_iso

_DEFAULT_FONT = 'default8x16'
_ENV_FONT = os.environ.get('FONT')


class ConsoleFont:
	def __init__(self) -> None:
		self._font_backup: Path | None = None
		self._cmap_backup: Path | None = None
		self.using_env_font = False

		self.active_font: str | None = None

	def save(self) -> None:
		"""Save the current console font (with unicode map) and console map to temp files."""
		if not running_from_iso():
			return

		font_fd, font_path = tempfile.mkstemp(prefix='archinstall_font_')
		cmap_fd, cmap_path = tempfile.mkstemp(prefix='archinstall_cmap_')
		os.close(font_fd)
		os.close(cmap_fd)
		self._font_backup = Path(font_path)
		self._cmap_backup = Path(cmap_path)

		try:
			SysCommand(['setfont', '-O', str(self._font_backup), '-om', str(self._cmap_backup)])
		except SysCallError as err:
			debug(f'Failed to save console font: {err}')
			self._font_backup = None
			self._cmap_backup = None

	def restore(self) -> None:
		"""Restore console font (with unicode map) and console map from backup."""
		if not running_from_iso():
			return

		if self._font_backup is None or not self._font_backup.exists():
			return

		cmd = ['setfont', str(self._font_backup)]
		if self._cmap_backup is not None and self._cmap_backup.exists():
			cmd += ['-m', str(self._cmap_backup)]
		try:
			SysCommand(cmd)
		except SysCallError as err:
			debug(f'Failed to restore console font: {err}')

		self._font_backup.unlink(missing_ok=True)
		self._font_backup = None
		if self._cmap_backup is not None:
			self._cmap_backup.unlink(missing_ok=True)
			self._cmap_backup = None

	def apply(self) -> None:
		"""Apply console font from FONT env var or active language mapping.

		If FONT env var is set and valid, use it and skip language mapping.
		If FONT is set but invalid, fall back to language font.
		If FONT is not set, use active language font.
		"""
		if not running_from_iso():
			return

		if _ENV_FONT:
			if self.set(_ENV_FONT):
				self.using_env_font = True
				debug(f'Console font set from FONT env var: {_ENV_FONT}')
			else:
				debug(f'FONT={_ENV_FONT} could not be set, falling back to language font mapping')
				if self.active_font:
					self.set(self.active_font)
					debug(f'Console font set from language mapping: {self.active_font}')
		elif self.active_font:
			self.set(self.active_font)
			debug(f'Console font set from language mapping: {self.active_font}')

	def set(self, font_name: str | None) -> bool:
		"""Set the console font via setfont. Only runs on ISO. Returns True on success."""
		if not running_from_iso():
			return False

		target = font_name or _DEFAULT_FONT
		try:
			SysCommand(['setfont', target])
			return True
		except SysCallError as err:
			debug(f'Failed to set console font {target}: {err}')
			return False
