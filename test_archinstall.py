import json
import archinstall

archinstall.update_drive_list(emulate=False)
archinstall.setup_args_defaults(archinstall.args, interactive=False)
#for drive in archinstall.harddrives:
#	print(drive, archinstall.human_disk_info(drive))

instructions = archinstall.load_automatic_instructions(emulate=False)
profile_instructions = archinstall.get_instructions('workstation', emulate=False)
profile_instructions = archinstall.merge_in_includes(profile_instructions, emulate=False)

print(json.dumps(archinstall.args, indent=4))