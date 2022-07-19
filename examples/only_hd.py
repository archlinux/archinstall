import logging
import os

from inspect import getsourcefile

if __name__ == '__main__':
	# to be able to execute simply as python examples/guided.py or (from inside examples python guided.py)
	# will work only with the copy at examples
	# this solution was taken from https://stackoverflow.com/questions/714063/importing-modules-from-parent-folder/33532002#33532002
	import sys
	current_path = os.path.abspath(getsourcefile(lambda: 0))
	current_dir = os.path.dirname(current_path)
	parent_dir = current_dir[:current_dir.rfind(os.path.sep)]
	sys.path.append(parent_dir)

import archinstall
from archinstall import ConfigurationOutput
from archinstall.examples.guided import perform_installation, perform_show_save_arguments


class OnlyHDMenu(archinstall.GlobalMenu):
	def _setup_selection_menu_options(self):
		super()._setup_selection_menu_options()
		options_list = []
		mandatory_list = []
		options_list = ['harddrives', 'disk_layouts', '!encryption-password','swap']
		mandatory_list = ['harddrives']
		options_list.extend(['save_config','install','abort'])

		for entry in self._menu_options:
			if entry in options_list:
				# for not lineal executions, only self.option(entry).set_enabled and set_mandatory are necessary
				if entry in mandatory_list:
					self.enable(entry,mandatory=True)
				else:
					self.enable(entry)
			else:
				self.option(entry).set_enabled(False)
		self._update_install_text()

	def mandatory_lacking(self) -> [int, list]:
		mandatory_fields = []
		mandatory_waiting = 0
		for field in self._menu_options:
			option = self._menu_options[field]
			if option.is_mandatory():
				if not option.has_selection():
					mandatory_waiting += 1
					mandatory_fields += [field,]
		return mandatory_fields, mandatory_waiting

	def _missing_configs(self):
		""" overloaded method """
		def check(s):
			return self.option(s).has_selection()

		missing, missing_cnt = self.mandatory_lacking()
		if check('harddrives'):
			if not self.option('harddrives').is_empty() and not check('disk_layouts'):
				missing_cnt += 1
				missing += ['disk_layout']
		return missing

def ask_user_questions():
	"""
		First, we'll ask the user for a bunch of user input.
		Not until we're satisfied with what we want to install
		will we continue with the actual installation steps.
	"""
	with OnlyHDMenu(data_store=archinstall.arguments) as menu:
		# We select the execution language separated
		menu.exec_option('archinstall-language')
		menu.option('archinstall-language').set_enabled(False)
		menu.run()

#
# script specific code
#


nomen = getsourcefile(lambda: 0)
script_name = nomen[nomen.rfind(os.path.sep) + 1:nomen.rfind('.')]
#
if __name__ in ('__main__',script_name):
	if not archinstall.arguments.get('silent'):
		ask_user_questions()

	perform_show_save_arguments()

	if archinstall.arguments.get('dry_run'):
		exit(0)

	if not archinstall.arguments.get('silent'):
		input(str(_('Press Enter to continue.')))

	archinstall.configuration_sanity_check()

	perform_installation(archinstall.storage.get('MOUNT_POINT', '/mnt'),'disk')
	# For support reasons, we'll log the disk layout post installation (crash or no crash)
	archinstall.log(f"Disk states after installing: {archinstall.disk_layouts()}", level=logging.DEBUG)
