from .manage_users_conf import ask_for_additional_users
from .locale_conf import select_locale_lang, select_locale_enc
from .system_conf import select_kernel, select_driver, ask_for_bootloader, ask_for_swap
from .network_conf import ask_to_configure_network
from .general_conf import (
	ask_ntp, ask_for_a_timezone, ask_for_audio_selection, select_language, select_mirror_regions,
	select_archinstall_language, ask_additional_packages_to_install,
	select_additional_repositories, ask_hostname, add_number_of_parrallel_downloads
)
from .utils import get_password
