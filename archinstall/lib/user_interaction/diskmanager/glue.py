# import archinstall
from ..system_conf import  select_harddrives
from archinstall.lib.storage import storage
from archinstall.lib.disk import BlockDevice
from archinstall.lib.user_interaction.diskmanager.discovery import layout_to_map, hw_discover
from archinstall.lib.user_interaction.diskmanager.generator import generate_layout
from archinstall.lib.user_interaction.diskmanager.partition_list import DevList
from archinstall.lib.user_interaction.partitioning_conf import get_default_partition_layout


def diskmanager(arguments,storage):

	status,list_layout = frontpage(arguments,storage)
	if not status:
		exit()
	if status == 'direct':
		return
	else:
		# pprint(list_layout)
		dl = DevList('*** Disk Layout ***', list_layout)
		result, partitions_to_delete = dl.run()
		if not result or dl.last_choice.value != dl._confirm_action:
			exit()
		arguments['disk_layouts'] = generate_layout(result)
		arguments['harddrives'] = [BlockDevice(key) for key in
											   arguments['disk_layouts']]
		# TODO
		arguments['partitions_to_delete'] = [partitions_to_delete[part.device],partitions_to_delete[part.uuid],partitions_to_delete[part.partnr]
											for part in partitions_to_delete]

def frontpage(arguments,storage):
	arguments = arguments
	storage = storage
	layout = {}
	if arguments.get('disk_layouts'):
		# TODO check if disks still exist
		# TODO fill missing arguments re physical layout
		layout = arguments.get('disk_layouts')
		harddrives = [BlockDevice(key) for key in layout]
		return 'ok',layout_to_map(harddrives,layout)
	else:
		prompt = '*** Disk Management ***'
		options = [
			str(_("Use whatever is defined at {} as the instalation target".format(storage['MOUNT_POINT']))),
			str(_('Select full disk(s), delete its contents and use a suggested layout')),
			str(_('Select disk(s) and manually manage them'),
			str(_('View full disk structure')
			str(_('Use old interface'))
		]
		result = Menu(prompt,options,skip=True,sort=False).run()
		if result:
			harddrives = []
			# use whatever exists at /mnt/archinstall
			if result.value == options[0]:
				# TODO should we check if the directory exists as a mountpoint ?
				arguments['harddrives'] = []
				if 'disk_layout' in arguments:
					del arguments['disk_layout']
				return "direct",None # patch, odious patch

			# select one or more disks and apply a standard layout
			standard_layout = None
			if result.value in (options[1],options[2]):
				old_harddrives = arguments.get('harddrives', [])
				harddrives = select_harddrives(old_harddrives)
				if not harddrives:
					return # TODO ought to be return to the menu
				arguments['harddrives'] = harddrives
				# in case the harddrives got changed we have to reset the disk layout as well
				# TODO is that needed now ?
				if old_harddrives != harddrives:
					arguments['disk_layouts'] = {}
				if result.value == options[1]:
					# we will create an standard layout, but will left open, editing it
					standard_layout = layout_to_map(get_default_partition_layout(harddrives))
				# elif result == options[2]:
					# layout = navigate_structure(arguments['harddrives'])
			elif result.value == options[3]:
				harddrives = []
				# layout = navigate_structure()
			elif result.value == options[4]:
				return 'direct',None
			else:
				pass
			my_layout = hw_discover(harddrives)
			if standard_layout:
				# TODO merge structure and standard
				pass
			else:
				return 'ok',my_layout
		else:
			return 'none',None
