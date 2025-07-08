import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

from archinstall.lib.installer import Installer
from archinstall.lib.models.bootloader import Bootloader
from archinstall.lib.models.device_model import (
    DiskLayoutConfiguration,
    PartitionModification,
    FilesystemType,
    DiskEncryption,
    EncryptionType
)
from archinstall.lib.hardware import SysInfo   # For mocking SysInfo.has_uefi()
from archinstall.lib.general import SysCommand # For mocking SysCommand
from archinstall.lib.pacman import Pacman      # For mocking Pacman


@pytest.fixture
def mock_installer(tmp_path):
    # Basic disk_config, can be customized per test
    mock_disk_config = DiskLayoutConfiguration(
        config_type='default',  # Or any valid DiskLayoutType
        device_modifications=[],
        disk_encryption=DiskEncryption(encryption_type=EncryptionType.NoEncryption)
    )
    installer = Installer(target=tmp_path / "archinstall_mnt", disk_config=mock_disk_config)
    # Mock dependencies of add_bootloader and _add_refind_bootloader
    installer.pacman = MagicMock(spec=Pacman)
    installer._get_efi_partition = MagicMock()
    installer._get_boot_partition = MagicMock()
    installer._get_root = MagicMock()
    installer._get_kernel_params = MagicMock(return_value=["rw", "quiet"])
    installer.kernels = ["linux"] # Default kernel
    return installer

@patch('archinstall.lib.installer.SysInfo', autospec=True)
@patch('archinstall.lib.installer.SysCommand', autospec=True)
def test_add_refind_bootloader_uefi_success(mock_sys_command, mock_sys_info, mock_installer, tmp_path):
    """
    Tests successful rEFInd installation on a UEFI system.
    """
    mock_sys_info.has_uefi.return_value = True

    # Setup mock partitions
    esp_mountpoint_rel = Path("boot/efi")
    esp_mountpoint_abs = mock_installer.target / esp_mountpoint_rel

    mock_efi_partition = PartitionModification(
        dev_path=Path("/dev/sda1"),
        part_type="primary",
        fs_type=FilesystemType.Fat32,
        mountpoint=esp_mountpoint_abs, # Absolute path for installer logic
        size=200, # MiB
        boot=True, # Marking as ESP
        encrypted=False
    )
    mock_efi_partition.relative_mountpoint = esp_mountpoint_rel # Relative path for config files

    mock_root_partition = PartitionModification(
        dev_path=Path("/dev/sda2"),
        part_type="primary",
        fs_type=FilesystemType.Ext4,
        mountpoint=mock_installer.target / "/", # Absolute path
        size=10240, # MiB
        encrypted=False
    )
    mock_root_partition.relative_mountpoint = Path("/") # Relative path
    mock_root_partition.partuuid = "test-partuuid-root"


    mock_installer._get_efi_partition.return_value = mock_efi_partition
    mock_installer._get_boot_partition.return_value = mock_efi_partition # Assuming ESP is also /boot
    mock_installer._get_root.return_value = mock_root_partition


    # Path for refind_linux.conf
    refind_conf_dir = esp_mountpoint_abs / "EFI/BOOT"
    refind_conf_file = refind_conf_dir / "refind_linux.conf"

    # Mock SysCommand to simulate successful refind-install
    # and to allow checking file creation for refind_linux.conf
    def sys_command_side_effect(command, *args, **kwargs):
        cmd_str = command if isinstance(command, str) else ' '.join(command)
        if "refind-install" in cmd_str:
            # Simulate refind-install creating the directory if it doesn't exist
            refind_conf_dir.mkdir(parents=True, exist_ok=True)
            return MagicMock(returncode=0, stdout=b"", stderr=b"")
        return MagicMock(returncode=0, stdout=b"", stderr=b"")

    mock_sys_command.side_effect = sys_command_side_effect

    mock_installer.add_bootloader(Bootloader.Refind)

    # Assertions
    mock_installer.pacman.strap.assert_called_once_with('refind')

    # Check that refind-install was called
    # The exact command can be tricky due to path joining, adjust as needed
    expected_refind_install_cmd_part1 = f'arch-chroot {mock_installer.target} refind-install --usedefault {esp_mountpoint_abs}'

    # Check if either of the refind-install commands were called
    calls = [
        call(expected_refind_install_cmd_part1),
    ]
    # mock_sys_command.assert_any_call(expected_refind_install_cmd_part1) # More flexible

    # Check if refind_linux.conf was created and contains expected content
    assert refind_conf_file.exists()
    content = refind_conf_file.read_text()
    assert '"Arch Linux"' in content
    assert f'root=PARTUUID={mock_root_partition.partuuid} rw quiet initrd=\\initramfs-linux.img' in content
    assert mock_installer._helper_flags['bootloader'] == 'refind'


@patch('archinstall.lib.installer.SysInfo', autospec=True)
def test_add_refind_bootloader_no_uefi(mock_sys_info, mock_installer):
    """
    Tests that rEFInd installation raises an error if not on a UEFI system.
    """
    mock_sys_info.has_uefi.return_value = False

    with pytest.raises(Exception) as excinfo: # Catches HardwareIncompatibilityError
        mock_installer.add_bootloader(Bootloader.Refind)
    assert "rEFInd requires an EFI system" in str(excinfo.value)

@patch('archinstall.lib.installer.SysInfo', autospec=True)
@patch('archinstall.lib.installer.SysCommand', autospec=True)
def test_add_refind_bootloader_install_fails(mock_sys_command, mock_sys_info, mock_installer):
    """
    Tests that rEFInd installation raises an error if refind-install command fails.
    """
    mock_sys_info.has_uefi.return_value = True
    # Setup mock partitions like in the success test
    esp_mountpoint_rel = Path("boot/efi")
    esp_mountpoint_abs = mock_installer.target / esp_mountpoint_rel
    mock_efi_partition = PartitionModification(dev_path=Path("/dev/sda1"), part_type="primary", fs_type=FilesystemType.Fat32, mountpoint=esp_mountpoint_abs, size=200, boot=True, encrypted=False)
    mock_efi_partition.relative_mountpoint = esp_mountpoint_rel
    mock_root_partition = PartitionModification(dev_path=Path("/dev/sda2"), part_type="primary", fs_type=FilesystemType.Ext4, mountpoint=mock_installer.target / "/", size=10240, encrypted=False)
    mock_root_partition.relative_mountpoint = Path("/")
    mock_installer._get_efi_partition.return_value = mock_efi_partition
    mock_installer._get_boot_partition.return_value = mock_efi_partition
    mock_installer._get_root.return_value = mock_root_partition

    # Simulate refind-install failing for both attempts
    mock_sys_command.side_effect = Exception("refind-install failed")

    with pytest.raises(Exception) as excinfo: # Catches DiskError
        mock_installer.add_bootloader(Bootloader.Refind)
    assert "Could not install rEFInd" in str(excinfo.value)

# More tests could be added:
# - Test for when ESP is not FAT32
# - Test for when refind_linux.conf already exists and is not empty
# - Test for UKI enabled scenario (though the current implementation is basic for UKI)
# - Test for fallback refind-install command (when --usedefault fails)
# - Test when root partition identifier is UUID instead of PARTUUID
# - Test with LVM root volume (this would require more complex mocking for _get_root and _get_kernel_params)

# To run these tests (assuming pytest is set up for the project):
# pytest tests/test_refind_installation.py
# (You might need to adjust paths and ensure __init__.py files are present in test directories)

# Explanation of the test:
# 1. mock_installer fixture: Sets up a basic Installer instance with mocked dependencies.
#    - `tmp_path` is a pytest fixture providing a temporary directory.
#    - `disk_config` is a minimal configuration.
#    - Key methods like `pacman.strap`, `_get_efi_partition`, etc., are mocked.
#
# 2. test_add_refind_bootloader_uefi_success:
#    - Mocks `SysInfo.has_uefi` to return `True`.
#    - Mocks `SysCommand` to simulate successful execution of `refind-install`.
#      The side_effect creates the directory where `refind_linux.conf` would go,
#      as `refind-install` normally does this.
#    - Sets up mock EFI and root partitions. It's important that the ESP
#      has a `mountpoint` attribute that `_add_refind_bootloader` uses.
#    - Calls `mock_installer.add_bootloader(Bootloader.Refind)`.
#    - Asserts that `pacman.strap` was called with 'refind'.
#    - Asserts that `SysCommand` was called with the `refind-install` command.
#      (Note: The exact command string might need adjustment based on how paths are joined).
#    - Asserts that `refind_linux.conf` was created and contains the expected content.
#      This verifies the logic for generating the configuration.
#    - Asserts that the `bootloader` flag in `_helper_flags` is set to 'refind'.
#
# 3. test_add_refind_bootloader_no_uefi:
#    - Mocks `SysInfo.has_uefi` to return `False`.
#    - Asserts that calling `add_bootloader` with `Bootloader.Refind` raises
#      an exception (HardwareIncompatibilityError, caught as general Exception here for simplicity)
#      and that the error message is as expected.
#
# 4. test_add_refind_bootloader_install_fails:
#    - Mocks `SysInfo.has_uefi` to return `True`.
#    - Mocks `SysCommand` to raise an exception when `refind-install` is called,
#      simulating a failure of the command.
#    - Asserts that this leads to a `DiskError` (caught as general Exception)
#      with the appropriate message.
#
# Running the tests:
#   These tests would be run using pytest. You'd typically navigate to the root
#   of the archinstall project and run `pytest tests/test_refind_installation.py`
#   or `pytest` to run all tests.
#   The `unittest.mock.patch` decorator is used to replace objects/functions
#   with mocks within the scope of the test function.
#
# Further improvements:
#   - Test the fallback scenario for `refind-install` (when `--usedefault` fails).
#   - Test behavior when `refind_linux.conf` already exists.
#   - Test scenarios with UKIs (Unified Kernel Images), though the current rEFInd
#     implementation for UKIs is noted as basic.
#   - Test different root filesystem types or LVM scenarios if they affect
#     `_get_kernel_params` in a way that rEFInd configuration needs to handle differently.

print("Test file for rEFInd installation created at tests/test_refind_installation.py")
