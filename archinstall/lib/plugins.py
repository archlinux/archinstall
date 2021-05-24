from importlib import metadata

plugins = {}

# 1: List archinstall.plugin definitions
# 2: Load the plugin entrypoint
# 3: Initiate the plugin and store it as .name in plugins
for plugin_definition in metadata.entry_points()['archinstall.plugin']:
	plugin_entrypoint = plugin_definition.load()
	plugins[plugin_definition.name] = plugin_entrypoint()