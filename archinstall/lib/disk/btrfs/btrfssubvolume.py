@dataclass
class BtrfsSubvolume:
	target :str
	source :str
	fstype :str
	name :str
	options :str
	root :bool = False

	def mount(self, mountpoint :Union[pathlib.Path, str]):
		pass