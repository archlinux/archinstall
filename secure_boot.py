__version__ = "2.2.0"

def on_load(installation):
    installation.arch_chroot("mkdir /etc/secure-boot")

def post_pacstrap(installation):
    installation.add_additional_packages("openssl  efitools sbsigntools")
    installation.arch_chroot("uuidgen --random > GUID.txt")
    installation.arch_chroot("openssl req -newkey rsa:4096 -nodes -keyout PK.key -new -x509 -sha256 -days 3650 -subj \"/CN=my Platform Key/\" -out  /etc/secure-boot/PK.crt && openssl x509 -outform DER -in  /etc/secure-boot/PK.crt -out  /etc/secure-boot/PK.cer && cert-to-efi-sig-list -g \"$(< GUID.txt)\"  /etc/secure-boot/PK.crt  /etc/secure-boot/PK.esl && sign-efi-sig-list -g \"$(< GUID.txt)\" -k  /etc/secure-boot/PK.key -c  /etc/secure-boot/PK.crt PK  /etc/secure-boot/PK.esl  /etc/secure-boot/PK.auth")
    installation.arch_chroot("sign-efi-sig-list -g \"$(< GUID.txt)\" -c  /etc/secure-boot/PK.crt -k  /etc/secure-boot/PK.key PK /dev/null  /etc/secure-boot/rm_PK.auth")
    installation.arch_chroot("openssl req -newkey rsa:4096 -nodes -keyout KEK.key -new -x509 -sha256 -days 3650 -subj \"/CN=my Key Exchange Key/\" -out  /etc/secure-boot/KEK.crt && openssl x509 -outform DER -in  /etc/secure-boot/KEK.crt -out  /etc/secure-boot/KEK.cer && cert-to-efi-sig-list -g \"$(< GUID.txt)\"  /etc/secure-boot/KEK.crt  /etc/secure-boot/KEK.esl && sign-efi-sig-list -g \"$(< GUID.txt)\" -k  /etc/secure-boot/PK.key -c  /etc/secure-boot/PK.crt KEK  /etc/secure-boot/KEK.esl  /etc/secure-boot/KEK.auth")
    installation.arch_chroot("openssl req -newkey rsa:4096 -nodes -keyout db.key -new -x509 -sha256 -days 3650 -subj \"/CN=my Signature Database key/\" -out  /etc/secure-boot/db.crt && openssl x509 -outform DER -in  /etc/secure-boot/db.crt -out  /etc/secure-boot/db.cer && cert-to-efi-sig-list -g \"$(< GUID.txt)\" /etc/secure-boot/db.crt  /etc/secure-boot/db.esl && sign-efi-sig-list -g \"$(< GUID.txt)\" -k  /etc/secure-boot/KEK.key -c  /etc/secure-boot/KEK.crt db  /etc/secure-boot/db.esl  /etc/secure-boot/db.auth")
    installation.arch_chroot("sbsign --key /etc/secure-boot/db.key --cert /etc/secure-boot/db.crt --output /boot/vmlinuz-linux /boot/vmlinuz-linux && sbsign --key /etc/secure-boot/db.key --cert /etc/secure-boot/db.crt --output /boot/EFI/BOOT/BOOTX64.EFI /boot/EFI/BOOT/BOOTX64.EFI")

def post_install(installation):
    installation.arch_chroot("cp /usr/share/libalpm/hooks/90-mkinitcpio-install.hook /etc/pacman.d/hooks/90-mkinitcpio-install.hook")
    installation.arch_chroot("sed -i 's/Exec = \\/usr\\/share\\/libalpm\\/scripts\\/mkinitcpio-install/Exec = \\/usr\\/local\\/share\\/libalpm\\/scripts\\/mkinitcpio-install/g'")
    installation.arch_chroot("cp /usr/lshare/libalpm/scripts/mkinitcpio-install /usr/local/share/libalpm/scripts/mkinitcpio-install")
    installation.arch_chroot("""sed -i 's/install -Dm644 "${line}" "/boot/vmlinuz-${pkgbase}"/sbsign --key \\/etc\\/secure-boot\\/db.key --cert \\/etc\\/secure-boot\\/db.crt --output "\\/boot\\/vmlinuz-${pkgbase}" "${line}"/g /usr/local/share/libalpm/scripts/mkinitcpio-install""")
    installation.arch_chroot(f"mv /etc/secure-boot/*.esl /boot/")