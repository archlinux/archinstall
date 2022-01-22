import json
import pathlib
import logging
"""
Here can be located all the routines which are deemed reusable for the scripts.
The only allowable import from the library is archinstall
"""
import archinstall
from archinstall.examples.commons import output_configs

def output_configs(show :bool=True, save :bool=True):
	""" Show on the screen the configuration data (except credentials) and/or save them on a json file
	:param show:Determines if the config data will be displayed on screen in Json format
	:type show: bool
	:param save:Determines if the config data will we written as a Json file
	:type save:bool
	"""
	user_credentials = {}
	disk_layout = {}
	user_config = {}
	for key in archinstall.arguments:
		if key in ['!users','!superusers','!encryption-password']:
			user_credentials[key] = archinstall.arguments[key]
		elif key == 'disk_layouts':
			disk_layout = archinstall.arguments[key]
		elif key in ['abort','install','config','creds','dry_run']:
			pass
		else:
			user_config[key] = archinstall.arguments[key]

	user_configuration_json = json.dumps({
		'config_version': archinstall.__version__, # Tells us what version was used to generate the config
		**user_config, # __version__ will be overwritten by old version definition found in config
		'version': archinstall.__version__
	} , indent=4, sort_keys=True, cls=archinstall.JSON)
	if disk_layout:
		disk_layout_json = json.dumps(disk_layout, indent=4, sort_keys=True, cls=archinstall.JSON)
	if user_credentials:
		user_credentials_json = json.dumps(user_credentials, indent=4, sort_keys=True, cls=archinstall.UNSAFE_JSON)

	if save:
		dest_path = pathlib.Path(archinstall.storage.get('LOG_PATH','.'))
		if (not dest_path.exists()) or not (dest_path.is_dir()):
			archinstall.log(f"Destination directory {dest_path.resolve()} does not exist or is not a directory,\n Configuration files can't be saved",fg="yellow",)
			input("Press enter to continue")
		else:
			with (dest_path / "user_configuration.json").open('w') as config_file:
				config_file.write(user_configuration_json)
			if user_credentials:
				target = dest_path / "user_credentials.json"
				with target.open('w') as config_file:
					config_file.write(user_credentials_json)
			if disk_layout:
				target = dest_path / "user_disk_layout.json"
				with target.open('w') as config_file:
					config_file.write(disk_layout_json)

	if show:
		print()
		print('This is your chosen configuration:')
		archinstall.log("-- Guided template chosen (with below config) --", level=logging.DEBUG)
		archinstall.log(user_configuration_json, level=logging.INFO)
		if disk_layout:
			archinstall.log(disk_layout_json, level=logging.INFO)
		print()
