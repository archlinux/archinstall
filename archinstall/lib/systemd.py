class Ini():
	def __init__(self, *args, **kwargs):
		"""
		Limited INI handler for now.
		Supports multiple keywords through dictionary list items.
		"""
		self.kwargs = kwargs

	def __str__(self):
		result = ''
		first_row_done = False
		for top_level in self.kwargs:
			if first_row_done:
				result += f"\n[{top_level}]\n"
			else:
				result += f"[{top_level}]\n"
				first_row_done = True

			for key, val in self.kwargs[top_level].items():
				if type(val) == list:
					for item in val:
						result += f"{key}={item}\n"
				else:
					result += f"{key}={val}\n"

		return result

class Systemd(Ini):
	def __init__(self, *args, **kwargs):
		"""
		Placeholder class to do systemd specific setups.
		"""
		super(Systemd, self).__init__(*args, **kwargs)

class Networkd(Systemd):
	def __init__(self, *args, **kwargs):
		"""
		Placeholder class to do systemd-network specific setups.
		"""
		super(Networkd, self).__init__(*args, **kwargs)