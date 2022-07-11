# import archinstall
from pudb import set_trace
from ..system_conf import  select_harddrives
from archinstall.lib.disk import BlockDevice
from archinstall.lib.menu import Menu
from archinstall.lib.user_interaction.diskmanager.discovery import layout_to_map, hw_discover
from archinstall.lib.user_interaction.diskmanager.generator import generate_layout
from archinstall.lib.user_interaction.diskmanager.partition_list import DevList
from archinstall.lib.user_interaction.partitioning_conf import get_default_partition_layout


def diskmanager(arguments,storage):

	status = 'show'
	while status == 'show':
		status,list_layout = frontpage(arguments,storage)
		if not status:
			exit()
		if status == 'direct':
			return

	# pprint(list_layout)
	dl = DevList('*** Disk Layout ***', list_layout)
	result, partitions_to_delete = dl.run()
	if not result or dl.last_choice.value != dl._confirm_action:
		exit()
	arguments['harddrives'],arguments['disk_layouts'] = generate_layout(result)
	# TODO
	arguments['partitions_to_delete'] = [[partitions_to_delete[part.device], partitions_to_delete[part.uuid], partitions_to_delete[part.partnr]]
										for part in partitions_to_delete]

def frontpage(arguments,storage):
	layout = {}
	if arguments.get('disk_layouts'):
		# TODO check if disks still exist
		# TODO fill missing arguments re physical layout
		layout = arguments.get('disk_layouts')
		return 'ok',layout_to_map(layout)
	else:
		prompt = '*** Disk Management ***'
		options = [
			str(_("Use whatever is defined at {} as the instalation target".format(storage['MOUNT_POINT']))),
			str(_('Select full disk(s), delete its contents and use a suggested layout')),
			str(_('Select disk(s) and manually manage them')),
			str(_('View full disk structure')),
			str(_('Use old interface'))
		]
		result = Menu(prompt,options,skip=True,sort=False).run()
		if result.value:
			harddrives = []
			# go to old interface
			if result.value == options[4]:
				return 'direct',None
			# use whatever exists at /mnt/archinstall
			if result.value == options[0]:
				# TODO this option seems to be borked now at master
				# TODO should we check if the directory exists as a mountpoint ?
				arguments['harddrives'] = []
				if 'disk_layout' in arguments:
					del arguments['disk_layout']
				return "direct",None # patch, odious patch

			# select one or more disks and apply a standard layout
			standard_layout = None
			if result.value in (options[1],options[2]):
				# TODO handle unintended gaps
				# TODO check with current structure ¿?
				# TODO in option 2 is there an option to get standard layout viable ¿? Is there need
				old_harddrives = arguments.get('harddrives', [])
				harddrives = select_harddrives(old_harddrives)
				if not harddrives:
					return 'show',None
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
			else:
				pass
			my_layout = hw_discover(harddrives)
			if standard_layout:
				# TODO merge structure and standard
				return 'ok',standard_layout
			else:
				return 'ok',my_layout
		else:
			return None,None
