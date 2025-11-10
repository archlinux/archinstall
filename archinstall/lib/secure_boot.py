from ..installer import Installer
from ..output import log
import os

def setup_secure_boot(installer: Installer):
    """
    Set up Secure Boot using sbctl.
    """
    if not installer.config.secure_boot:
        return

    log("Setting up Secure Boot...", level="v")

    # Install sbctl
    installer.add_additional_packages("sbctl")

    # Create keys
    installer.run_command("sbctl create-keys")

    # Enroll keys
    if installer.config.secure_boot_option == "ms":
        installer.run_command("sbctl enroll-keys -m")
    else:
        # rhboot's UEFI shim loader
        installer.add_additional_packages("shim-signed")
        
        boot_efi_boot_dir = os.path.join(installer.target, "boot/EFI/BOOT")
        if not os.path.exists(boot_efi_boot_dir):
            os.makedirs(boot_efi_boot_dir)

        installer.run_command(f"cp /usr/share/shim-signed/shimx64.efi {boot_efi_boot_dir}/BOOTX64.EFI")
        installer.run_command(f"cp /usr/share/shim-signed/mmx64.efi {boot_efi_boot_dir}/")
        installer.run_command("sbctl enroll-keys -m")
    elif installer.config.secure_boot_option == "valdikss":
        log("Setting up Super-UEFIinSecureBoot-Disk...", level="v")
        installer.add_additional_packages("unzip")
        installer.run_command("wget https://github.com/valdikSS/Super-UEFIinSecureBoot-Disk/archive/refs/heads/master.zip -O /tmp/super-uefi.zip")
        installer.run_command("unzip /tmp/super-uefi.zip -d /tmp/super-uefi")
        
        esp_path = installer.config.boot_partition
        if esp_path:
            boot_efi_boot_dir = os.path.join(installer.target, str(esp_path).lstrip('/'), "EFI/BOOT")
            if not os.path.exists(boot_efi_boot_dir):
                os.makedirs(boot_efi_boot_dir)
            
            installer.run_command(f"cp /tmp/super-uefi/Super-UEFIinSecureBoot-Disk-master/EFI/BOOT/bootx64.efi {boot_efi_boot_dir}/")
            installer.run_command(f"cp /tmp/super-uefi/Super-UEFIinSecureBoot-Disk-master/keys/DB.auth {boot_efi_boot_dir}/")
            installer.run_command(f"sbctl enroll-keys --custom {boot_efi_boot_dir}/DB.auth")
        else:
            log("Could not find boot partition, skipping Super-UEFIinSecureBoot-Disk setup.", level="warning")

    # Sign the bootloader
    esp_path = installer.config.boot_partition
    if esp_path:
        installer.run_command(f"sbctl sign -s {esp_path}/EFI/BOOT/BOOTX64.EFI")
        if os.path.exists(os.path.join(installer.target, str(esp_path).lstrip('/'), "EFI/systemd/systemd-bootx64.efi")):
            installer.run_command(f"sbctl sign -s {esp_path}/EFI/systemd/systemd-bootx64.efi")
        
        for kernel in installer.kernels:
            if os.path.exists(os.path.join(installer.target, str(esp_path).lstrip('/'), f"vmlinuz-{kernel}")):
                installer.run_command(f"sbctl sign -s {esp_path}/vmlinuz-{kernel}")
    else:
        log("Could not find boot partition, skipping signing.", level="warning")

    log("Secure Boot setup complete.", level="v")