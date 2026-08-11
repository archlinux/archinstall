from pathlib import Path

from archinstall.lib.models.application import (
	ApplicationConfiguration,
	Audio,
	AudioConfiguration,
	BluetoothConfiguration,
	FirewallConfiguration,
	FontPackage,
	FontsConfigSerialization,
	FontsConfiguration,
	PrintServiceConfiguration,
	ZramAlgorithm,
	ZramConfiguration,
)
from archinstall.lib.models.authentication import AuthenticationConfiguration, U2FLoginConfiguration, U2FLoginMethod
from archinstall.lib.models.bootloader import Bootloader, BootloaderConfiguration, PlymouthTheme
from archinstall.lib.models.config import SummaryLevel
from archinstall.lib.models.device import DiskLayoutConfiguration, DiskLayoutType
from archinstall.lib.models.locale import LocaleConfiguration
from archinstall.lib.models.mirrors import (
	CustomRepository,
	CustomServer,
	MirrorConfiguration,
	MirrorRegion,
	SignCheck,
	SignOption,
)
from archinstall.lib.models.network import NetworkConfiguration, Nic, NicType
from archinstall.lib.models.pacman import PacmanConfiguration
from archinstall.lib.models.users import Password, User


def test_bootloader_summary_basic_omits_inactive_options() -> None:
	config = BootloaderConfiguration(bootloader=Bootloader.Systemd, uki=False, removable=False)

	assert config.summary() == ['Bootloader "Systemd-boot"']


def test_bootloader_summary_detailed_includes_defaults() -> None:
	config = BootloaderConfiguration(bootloader=Bootloader.Systemd, uki=False, removable=False)

	assert config.summary(SummaryLevel.Detailed) == [
		'Bootloader "Systemd-boot"',
		'UKI disabled',
		'Not removable',
		'Plymouth disabled',
	]


def test_bootloader_summary_detailed_includes_plymouth_theme() -> None:
	config = BootloaderConfiguration(
		bootloader=Bootloader.Grub,
		uki=True,
		removable=True,
		plymouth=PlymouthTheme.SPINNER,
	)

	assert config.summary(SummaryLevel.Detailed) == [
		'Bootloader "Grub"',
		'UKI enabled',
		'Removable',
		'Plymouth "spinner"',
	]


def test_locale_summary_identical_for_both_levels() -> None:
	config = LocaleConfiguration(kb_layout='us', sys_lang='en_US.UTF-8', sys_enc='UTF-8')

	assert config.summary() == config.summary(SummaryLevel.Detailed)
	assert config.summary() == [
		'Keyboard layout "us"',
		'Locale language "en_US.UTF-8"',
		'Locale encoding "UTF-8"',
		'Console font "default8x16"',
	]


def test_pacman_summary_includes_parallel_downloads_and_color() -> None:
	config = PacmanConfiguration(parallel_downloads=7, color=False)

	assert config.summary() == [
		'Parallel downloads "7"',
		'Color disabled',
	]
	assert config.summary(SummaryLevel.Detailed) == config.summary()


def test_zram_summary_basic_hides_disabled() -> None:
	assert ZramConfiguration(enabled=False).summary() is None


def test_zram_summary_detailed_shows_disabled() -> None:
	assert ZramConfiguration(enabled=False).summary(SummaryLevel.Detailed) == ['Zram disabled']


def test_zram_summary_enabled_includes_algorithm() -> None:
	config = ZramConfiguration(enabled=True, algorithm=ZramAlgorithm.LZ4)

	assert config.summary() == ['Zram enabled', 'Zram algorithm lz4']


def test_network_summary_basic_hides_nic_detail() -> None:
	config = NetworkConfiguration(
		type=NicType.MANUAL,
		nics=[Nic(iface='eno1', ip='192.168.1.15/24', dhcp=False, gateway='192.168.1.1', dns=['9.9.9.9'])],
	)

	assert config.summary() == ['Manual configuration']


def test_network_summary_detailed_includes_static_nic_detail() -> None:
	config = NetworkConfiguration(
		type=NicType.MANUAL,
		nics=[Nic(iface='eno1', ip='192.168.1.15/24', dhcp=False, gateway='192.168.1.1', dns=['9.9.9.9', '1.1.1.1'])],
	)

	assert config.summary(SummaryLevel.Detailed) == [
		'Manual configuration',
		'eno1',
		'IP address "192.168.1.15/24"',
		'Gateway "192.168.1.1"',
		'DNS servers "9.9.9.9, 1.1.1.1"',
	]


def test_network_summary_detailed_dhcp_nic() -> None:
	config = NetworkConfiguration(type=NicType.MANUAL, nics=[Nic(iface='eno1', dhcp=True)])

	assert config.summary(SummaryLevel.Detailed) == [
		'Manual configuration',
		'eno1',
		'DHCP enabled',
	]


def _mirror_config() -> MirrorConfiguration:
	return MirrorConfiguration(
		mirror_regions=[MirrorRegion(name='Australia', urls=['http://mirror.example.com/$repo/os/$arch'])],
		custom_servers=[CustomServer('https://mymirror.com/$repo/os/$arch')],
		custom_repositories=[
			CustomRepository(
				name='myrepo',
				url='https://myrepo.com/$repo/os/$arch',
				sign_check=SignCheck.Required,
				sign_option=SignOption.TrustAll,
			),
		],
	)


def test_mirror_summary_basic_hides_urls() -> None:
	assert _mirror_config().summary() == [
		'Mirror regions "Australia"',
		'Custom servers set up',
		'Custom repositories set up',
	]


def test_mirror_summary_detailed_includes_urls() -> None:
	assert _mirror_config().summary(SummaryLevel.Detailed) == [
		'Region "Australia" with servers http://mirror.example.com/$repo/os/$arch',
		'Server "https://mymirror.com/$repo/os/$arch"',
		'Repository "myrepo" at https://myrepo.com/$repo/os/$arch (sign check Required, sign option TrustAll)',
	]


def _app_config() -> ApplicationConfiguration:
	return ApplicationConfiguration(
		bluetooth_config=BluetoothConfiguration(enabled=False),
		audio_config=AudioConfiguration(audio=Audio.PIPEWIRE),
		print_service_config=PrintServiceConfiguration(enabled=False),
		fonts_config=FontsConfiguration.parse_arg(FontsConfigSerialization(fonts=[FontPackage.NOTO.value])),
	)


def test_application_summary_basic_omits_disabled_features() -> None:
	assert _app_config().summary() == [
		'Audio server "pipewire"',
		'Extra fonts "noto-fonts"',
	]


def test_application_summary_detailed_shows_disabled_features() -> None:
	assert _app_config().summary(SummaryLevel.Detailed) == [
		'Bluetooth disabled',
		'Audio server "pipewire"',
		'Print service disabled',
		'Extra fonts "noto-fonts"',
	]


def test_application_summary_omits_unset_nested_configs() -> None:
	config = ApplicationConfiguration(firewall_config=FirewallConfiguration.parse_arg({'firewall': 'ufw'}))

	assert config.summary(SummaryLevel.Detailed) == ['Firewall "ufw"']


def _auth_config() -> AuthenticationConfiguration:
	return AuthenticationConfiguration(
		root_enc_password=Password(enc_password='hash'),
		users=[
			User(username='alice', password=Password(enc_password='hash'), sudo=True, groups=['wheel']),
			User(username='bob', password=Password(enc_password='hash'), sudo=False),
		],
		u2f_config=U2FLoginConfiguration(
			u2f_login_method=U2FLoginMethod.Passwordless,
			passwordless_sudo=True,
		),
	)


def test_auth_summary_basic_uses_counts() -> None:
	assert _auth_config().summary() == [
		'Root password set',
		'Configured 2 user(s)',
		'U2F set up',
	]


def test_auth_summary_detailed_lists_users_without_secrets() -> None:
	summary = _auth_config().summary(SummaryLevel.Detailed)

	assert summary == [
		'Root password set',
		'User "alice" (sudo, groups wheel)',
		'User "bob" (no sudo)',
		'U2F login method "Passwordless login"',
		'U2F passwordless sudo enabled',
	]
	assert not any('hash' in line for line in summary)


def test_auth_summary_detailed_reports_missing_root_password() -> None:
	assert AuthenticationConfiguration().summary(SummaryLevel.Detailed) == ['Root password not set']


def test_disk_summary_detailed_includes_mountpoint_for_pre_mounted() -> None:
	config = DiskLayoutConfiguration(config_type=DiskLayoutType.Pre_mount, mountpoint=Path('/mnt'))

	assert config.summary() == ['Pre-mount layout']
	assert config.summary(SummaryLevel.Detailed) == [
		'Pre-mount layout',
		'Mountpoint "/mnt"',
	]
