from typing import TYPE_CHECKING

from archinstall.lib.models.application import Editor, EditorConfiguration
from archinstall.lib.output import debug

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer


class EditorApp:
	@property
	def nano_package(self) -> list[str]:
		return ['nano']

	@property
	def micro_package(self) -> list[str]:
		return ['micro']

	@property
	def vi_package(self) -> list[str]:
		return ['vi']

	@property
	def vim_package(self) -> list[str]:
		return ['vim']

	@property
	def neovim_package(self) -> list[str]:
		return ['neovim']

	@property
	def emacs_package(self) -> list[str]:
		return ['emacs']

	def _get_editor_binary(self, editor: Editor) -> str:
		"""Return the binary name for the EDITOR environment variable."""
		match editor:
			case Editor.NANO:
				return 'nano'
			case Editor.MICRO:
				return 'micro'
			case Editor.VI:
				return 'vi'
			case Editor.VIM:
				return 'vim'
			case Editor.NEOVIM:
				return 'nvim'
			case Editor.EMACS:
				return 'emacs'

	def install(
		self,
		install_session: 'Installer',
		editor_config: EditorConfiguration,
	) -> None:
		debug(f'Installing editor: {editor_config.editor.value}')

		match editor_config.editor:
			case Editor.NANO:
				install_session.add_additional_packages(self.nano_package)
			case Editor.MICRO:
				install_session.add_additional_packages(self.micro_package)
			case Editor.VI:
				install_session.add_additional_packages(self.vi_package)
			case Editor.VIM:
				install_session.add_additional_packages(self.vim_package)
			case Editor.NEOVIM:
				install_session.add_additional_packages(self.neovim_package)
			case Editor.EMACS:
				install_session.add_additional_packages(self.emacs_package)

		editor_binary = self._get_editor_binary(editor_config.editor)
		environment_path = install_session.target / 'etc' / 'environment'

		debug(f'Setting EDITOR={editor_binary} in {environment_path}')

		# Append EDITOR to /etc/environment
		with open(environment_path, 'a') as f:
			f.write(f'EDITOR={editor_binary}\n')
