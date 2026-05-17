import shlex
from typing import TYPE_CHECKING

from archinstall.lib.exceptions import PackageError, SysCallError
from archinstall.lib.models.aur import AURHelperConfiguration
from archinstall.lib.models.users import User
from archinstall.lib.output import debug, info
from archinstall.lib.translationhandler import tr

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer


class AURHelperApp:
	"""Bootstraps an AUR helper (paru / yay) inside the chroot.

	The helper package name comes from a controlled ``AURHelper`` enum value,
	and the build username is validated upstream by archinstall's user-creation
	path, so shell interpolation of these values is safe. Dynamic file system
	paths are still passed through ``shlex.quote``.
	"""

	_SUDOERS_FILE = 'etc/sudoers.d/99_aur_build'

	def install(
		self,
		install_session: Installer,
		helper_config: AURHelperConfiguration,
		build_user: User,
	) -> None:
		install_session.add_additional_packages(['base-devel', 'git'])

		sudoers_path = install_session.target / self._SUDOERS_FILE
		sudoers_path.write_text(f'{build_user.username} ALL=(ALL) NOPASSWD: /usr/bin/pacman\n')
		sudoers_path.chmod(0o440)

		helper_pkg = helper_config.helper.value
		# Build inside the user's $HOME rather than /tmp: arch-chroot -S spawns a
		# transient systemd-run unit and the chroot's /tmp is the on-disk
		# directory (mode 0755, root-owned) since no boot-time tmpfs mount has
		# happened, so non-root writes to /tmp fail. Build tools like Go also
		# default TMPDIR to /tmp, so we redirect TMPDIR for the same reason.
		build_subdir = f'.cache/aur-build/{helper_pkg}'
		quoted_build = shlex.quote(build_subdir)
		tmp_env = 'TMPDIR="$HOME/.cache/aur-build/tmp"'

		try:
			info(tr('Installing AUR helper {}').format(helper_config.helper.value))
			install_session.arch_chroot(
				f'rm -rf -- {quoted_build} && mkdir -p -- "$HOME/.cache/aur-build/tmp" "$(dirname -- {quoted_build})"',
				run_as=build_user.username,
			)
			install_session.arch_chroot(
				f'git clone https://aur.archlinux.org/{helper_pkg}.git {quoted_build}',
				run_as=build_user.username,
			)
			install_session.arch_chroot(
				f'cd {quoted_build} && {tmp_env} makepkg -si --noconfirm',
				run_as=build_user.username,
			)
			install_session.arch_chroot(
				f'rm -rf -- {quoted_build} "$HOME/.cache/aur-build/tmp"',
				run_as=build_user.username,
			)
		except SysCallError as e:
			debug(f'AUR helper install failed: {e}')
			raise PackageError(tr('Failed to install AUR helper: {}').format(e)) from e
		finally:
			sudoers_path.unlink(missing_ok=True)
