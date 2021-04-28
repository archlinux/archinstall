import importlib.util
from archinstall import __version__

def load_plugin(path):
    name = path.split("/")[-1].strip(".py")
    plugin_load = importlib.util.spec_from_file_location(name,path)
    plugin = importlib.util.module_from_spec(plugin_load)
    plugin_load.loader.exec_module(plugin)
    if plugin_is_compatible(plugin):
        return {"name":name,"plugin":plugin}

    return None

def plugin_is_compatible(plugin) ->bool:
    if int(plugin.__version__) >=int(__version__):
        return True
    else:
        return False