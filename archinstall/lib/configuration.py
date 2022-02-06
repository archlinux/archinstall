import json
import pathlib
import logging
from .storage import storage
from .general import JSON, UNSAFE_JSON
from .output import log

def output_configs(area :dict, show :bool = True, save :bool = True):
	""" Show on the screen the configuration data (except credentials) and/or save them on a json file
	:param area: a dictionary to be shown/save (basically archinstall.arguments, but needed to be passed explictly to avoid circular references
	:type area: dict
	:param show:Determines if the config data will be displayed on screen in Json format
	:type show: bool
	:param save:Determines if the config data will we written as a Json file
	:type save:bool
	"""
	user_credentials = {}
	disk_layout = {}
	user_config = {}
	for key in area:
		if key in ['!users','!superusers','!encryption-password']:
			user_credentials[key] = area[key]
		elif key == 'disk_layouts':
			disk_layout = area[key]
		elif key in ['abort','install','config','creds','dry_run']:
			pass
		else:
			user_config[key] = area[key]

	user_configuration_json = json.dumps({
		'config_version': storage['__version__'], # Tells us what version was used to generate the config
		**user_config, # __version__ will be overwritten by old version definition found in config
		'version': storage['__version__']
	} , indent=4, sort_keys=True, cls=JSON)
	if disk_layout:
		disk_layout_json = json.dumps(disk_layout, indent=4, sort_keys=True, cls=JSON)
	if user_credentials:
		user_credentials_json = json.dumps(user_credentials, indent=4, sort_keys=True, cls=UNSAFE_JSON)

	if save:
		dest_path = pathlib.Path(storage.get('LOG_PATH','.'))
		if (not dest_path.exists()) or not (dest_path.is_dir()):
			log(f"Destination directory {dest_path.resolve()} does not exist or is not a directory,\n Configuration files can't be saved",fg="yellow",)
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
		log("-- Guided template chosen (with below config) --", level=logging.DEBUG)
		log(user_configuration_json, level=logging.INFO)
		if disk_layout:
			log(disk_layout_json, level=logging.INFO)
		print()
