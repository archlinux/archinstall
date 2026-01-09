from typing import TYPE_CHECKING

from archinstall.lib.models.application import Editor, EditorConfiguration
from archinstall.lib.output import debug

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer


class EditorApp:
	def _get_editor_binary(self, editor: Editor) -> str:
		# special handling only name that differs
		return 'nvim' if editor == Editor.NEOVIM else editor.value

	def install(
		self,
		install_session: 'Installer',
		editor_config: EditorConfiguration,
	) -> None:
		debug(f'Installing editor: {editor_config.editor.value}')

		install_session.add_additional_packages([editor_config.editor.value])

		editor_binary = self._get_editor_binary(editor_config.editor)
		environment_path = install_session.target / 'etc' / 'environment'

		debug(f'Setting EDITOR={editor_binary} in {environment_path}')

		with open(environment_path, 'a') as f:
			f.write(f'EDITOR={editor_binary}\n')
