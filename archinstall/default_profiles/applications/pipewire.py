from typing import TYPE_CHECKING, override

from archinstall.default_profiles.profile import Profile, ProfileType

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer
	from archinstall.lib.models.users import User


class PipewireProfile(Profile):
	def __init__(self) -> None:
		super().__init__("Pipewire", ProfileType.Application)

	@property
	@override
	def packages(self) -> list[str]:
		return [
			"pipewire",
			"pipewire-alsa",
			"pipewire-jack",
			"pipewire-pulse",
			"gst-plugin-pipewire",
			"libpulse",
			"wireplumber",
		]

	def _enable_pipewire_for_all(self, install_session: "Installer") -> None:
		from archinstall.lib.args import arch_config_handler

		users: list[User] | None = arch_config_handler.config.users

		if users is None:
			return

		for user in users:
			# Create the full path for enabling the pipewire systemd items
			service_dir = install_session.target / "home" / user.username / ".config" / "systemd" / "user" / "default.target.wants"
			service_dir.mkdir(parents=True, exist_ok=True)

			# Set ownership of the entire user catalogue
			install_session.arch_chroot(f"chown -R {user.username}:{user.username} /home/{user.username}")

			# symlink in the correct pipewire systemd items
			install_session.arch_chroot(
				f"ln -sf /usr/lib/systemd/user/pipewire-pulse.service /home/{user.username}/.config/systemd/user/default.target.wants/pipewire-pulse.service",
				run_as=user.username,
			)
			install_session.arch_chroot(
				f"ln -sf /usr/lib/systemd/user/pipewire-pulse.socket /home/{user.username}/.config/systemd/user/default.target.wants/pipewire-pulse.socket",
				run_as=user.username,
			)

	@override
	def install(self, install_session: "Installer") -> None:
		super().install(install_session)
		install_session.add_additional_packages(self.packages)
		self._enable_pipewire_for_all(install_session)
