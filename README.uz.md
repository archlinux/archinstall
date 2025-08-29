<!-- <div align="center"> -->
<img src="https://github.com/archlinux/archinstall/raw/master/docs/logo.png" alt="drawing" width="200"/>

<!-- Language Switcher -->
[🇬🇧 English](README.md) | [🇷🇺 Русский](README.ru.md) | [🇺🇿 O'zbekcha](README.uz.md)

<!-- </div> -->
# Arch Installer
[![Lint Python and Find Syntax Errors](https://github.com/archlinux/archinstall/actions/workflows/flake8.yaml/badge.svg)](https://github.com/archlinux/archinstall/actions/workflows/flake8.yaml)

Just another guided/automated [Arch Linux](https://wiki.archlinux.org/index.php/Arch_Linux) o‘rnatuvchisi o‘ziga xos yondashuv bilan.  
O‘rnatuvchi shuningdek, Arch Linux’ni o‘rnatish va o‘rnatilgan tizim ichidagi xizmatlar, paketlar hamda boshqa narsalarni boshqarish uchun Python kutubxonasi sifatida ham xizmat qiladi *(odatda live medium’dan)*.

* archinstall [discord](https://discord.gg/aDeMffrxNg) сервери
* archinstall [#archinstall:matrix.org](https://matrix.to/#/#archinstall:matrix.org) Matrix канали
* archinstall [#archinstall@irc.libera.chat:6697](https://web.libera.chat/?channel=#archinstall)
* archinstall [ҳужжатлар](https://archinstall.archlinux.page/)

# O'rnatish va Foydalanish
```shell
sudo pacman -S archinstall
```

O'rnatishning boshqa usullari: `git clone` orqali repozitoriyani klonlash yoki `pip install --upgrade archinstall`.

## [Guided](https://github.com/archlinux/archinstall/blob/master/archinstall/scripts/guided.py) installer-ni ishga tushirish

Agar siz Arch Linux live-ISO-da bo‘lsangiz yoki `pip` orqali o‘rnatgan bo‘lsangiz:  
```shell
archinstall
```

## `git` orqali [guided](https://github.com/archlinux/archinstall/blob/master/archinstall/scripts/guided.py) installer-ni ishga tushirish

```shell
    # cd archinstall-git
    # python -m archinstall
```

#### Kengaytirilgan
Ko‘pchilik foydalanuvchilar uchun kerak bo‘lmagan qo‘shimcha opsiyalar `--advanced` bayrog‘i ortida yashirilgan.

## Deklarativ konfiguratsiya fayli yoki URL orqali ishga tushirish

`archinstall` JSON konfiguratsiya fayli bilan ishlatilishi mumkin. Ikkita turli konfiguratsiya faylini hisobga olish kerak:  
`user_configuration.json` umumiy o‘rnatish sozlamalarini o‘z ichiga oladi,  
`user_credentials.json` esa foydalanuvchi paroli, root paroli va shifrlash paroli kabi maxfiy foydalanuvchi sozlamalarini o‘z ichiga oladi.

Foydalanuvchi konfiguratsiya fayli misolini bu yerdan topishingiz mumkin:  
[configuration file](https://github.com/archlinux/archinstall/blob/master/examples/config-sample.json)  
Va credentials konfiguratsiyasi misoli bu yerdan:  
[credentials file](https://github.com/archlinux/archinstall/blob/master/examples/creds-sample.json)

**MASLAHAT:** Konfiguratsiya fayllari `archinstall` ni ishga tushirib, barcha kerakli menyu punktlarini sozlaganingizdan so‘ng `Save configuration` tugmasini bosish orqali avtomatik yaratilishi mumkin.

Konfiguratsiya faylini `archinstall` ga yuklash uchun quyidagi komandani bajaring:
```shell
archinstall --config <path to user config file or URL> --creds <path to user credentials config file or URL>
```

### Credentials konfiguratsiya faylini shifrlash
Standart bo‘yicha barcha foydalanuvchi hisob ma’lumotlari `yescrypt` bilan hash qilinadi va saqlangan `user_credentials.json` faylida faqat hash saqlanadi.  
Disk shifrlash paroli uchun bu mumkin emas, chunki uni qo‘llash uchun ochiq matn shaklida saqlash zarur.

Biroq, konfiguratsiya fayllarini saqlashni tanlaganingizda, `archinstall` `user_credentials.json` faylini shifrlash opsiyasini so‘raydi.  
Faylni shifrlash uchun shifrlash parolini kiritish talab qilinadi.  
`--creds <user_credentials.json>` argumenti bilan shifrlangan `user_configuration.json` ni taqdim etganda, dekripsiya kalitini berishning bir nechta usullari mavjud:
* Dekripsiya kalitini komandani satr argumenti orqali taqdim eting: `--creds-decryption-key <password>`  
* Shifrlash kalitini `ARCHINSTALL_CREDS_DECRYPTION_KEY` atrof-muhit o‘zgaruvchisida saqlang, u avtomatik o‘qiladi  
* Agar yuqoridagilardan hech biri taqdim etilmasa, dekripsiya kalitini qo‘lda kiritish uchun so‘rov oynasi ko‘rsatiladi


# Yordam yoki Muammolar

Agar biror muammo yuzaga kelsa, iltimos, uni Github-da yuboring yoki savolingizni [discord](https://discord.gg/aDeMffrxNg) yordam kanalida post qiling.

Muammo yuborayotganda, iltimos:
* Agar mavjud bo‘lsa, chiqishdagi stacktrace ni taqdim eting
* Muammo tiketi bilan birga `/var/log/archinstall/install.log` faylini biriktiring. Bu bizga sizga yordam berishni osonlashtiradi!
  * ISO tasviridan log faylini olishning bir usuli:<br>
    ```shell
    curl -F'file=@/var/log/archinstall/install.log' https://0x0.st
    ```


# Mavjud tillar

Archinstall turli tillarda mavjud bo‘lib, ular jamoa tomonidan qo‘shilgan va qo‘llab-quvvatlanadi.  
Tilni installer ichida (birinchi menyu bandi) o‘zgartirish mumkin. E’tibor bering, barcha tillar to‘liq tarjimani taqdim etmaydi, chunki tarjimalar qo‘shgan foydalanuvchilarga bog‘liq. Har bir til qanchalik tarjima qilinganini ko‘rsatuvchi indikatorga ega.

Tarjimalarga qo‘shilgan har qanday hissa juda qadrlanadi.  
Boshlash uchun iltimos, [qo‘llanmani](https://github.com/archlinux/archinstall/blob/master/archinstall/locales/README.md) kuzating.

## Shriftlar
ISO turli tillar uchun kerakli barcha shriftlarni o‘z ichiga olmaydi.  
Lotin xarakterlaridan farq qiladigan shriftlar to‘g‘ri ko‘rsatilmaydi. Agar ushbu tillar tanlanmoqchi bo‘lsa, mos shrift konsolda qo‘lda sozlanishi kerak.

Barcha mavjud konsol shriftlarini `/usr/share/kbd/consolefonts` papkasida topish mumkin va `setfont LatGrkCyr-8x16` bilan o‘rnatish mumkin.


# O‘z o‘rnatishingizni skriptlash

## Interaktiv o‘rnatishni skriptlash

To‘liq skriptlangan, interaktiv o‘rnatish misoli uchun quyidagi misolga murojaat qiling:  
[interactive_installation.py](https://github.com/archlinux/archinstall/blob/master/archinstall/scripts/guided.py)


> **Ushbu skript bilan o‘z ISOingizni yaratish uchun:** O‘z ISOingizni yaratish bo‘yicha [ArchISO](https://wiki.archlinux.org/index.php/archiso) qo‘llanmasiga amal qiling.

## Non-interaktiv avtomatlashtirilgan o‘rnatish skripti

To‘liq skriptlangan, avtomatlashtirilgan o‘rnatish misoli uchun quyidagi misolga murojaat qiling:  
[full_automated_installation.py](https://github.com/archlinux/archinstall/blob/master/examples/full_automated_installation.py)

# Profillar

`archinstall` o‘rnatish jarayonida tanlash mumkin bo‘lgan oldindan sozlangan profillar to‘plami bilan birga keladi.

- [Desktop](https://github.com/archlinux/archinstall/tree/master/archinstall/default_profiles/desktops)
- [Server](https://github.com/archlinux/archinstall/tree/master/archinstall/default_profiles/servers)

Profillarning ta’riflari va ular o‘rnatadigan paketlarni menyuda bevosita ko‘rish yoki [default profiles](https://github.com/archlinux/archinstall/tree/master/archinstall/default_profiles) orqali tekshirish mumkin.

# Sinov

## Live ISO tasviridan foydalanish

Agar siz repozitoriyadan commit, branch yoki so‘nggi chiqarilgan versiyani standart Arch Linux Live ISO tasviri yordamida sinamoqchi bo‘lsangiz, `archinstall` versiyasini yangi versiya bilan almashtiring va quyida ko‘rsatilgan qadamlarni bajaring.

*Eslatma: Live USB dan yuklanayotganda, ramdiskdagi joy cheklangan bo‘lishi mumkin va installerning qayta o‘rnatilishi yoki yangilanishi uchun yetarli bo‘lmasligi mumkin. Agar bu muammo yuzaga kelsa, quyidagilardan birini ishlatish mumkin:
- Root bo‘limini qayta o‘lchash https://wiki.archlinux.org/title/Archiso#Adjusting_the_size_of_the_root_file_system  
- Boot parametr `copytoram=y` (https://gitlab.archlinux.org/archlinux/mkinitcpio/mkinitcpio-archiso/-/blob/master/docs/README.bootparams#L26) belgilanishi mumkin, bu root fayl tizimini tmpfs ga ko‘chiradi.*

1. Sizga ishlayotgan tarmoq ulanishi kerak  
2. Qurilish talablarini o‘rnating: `pacman -Sy; pacman -S git python-pip gcc pkgconf`  
   *(e’tibor bering, bu RAM va hozirgi squashfs fayl tizimining bo‘sh joyiga bog‘liq holda ishlashi yoki ishlamasligi mumkin)*  
3. Oldingi `archinstall` versiyasini o‘rnatuvchidan o‘chirib tashlang: `pip uninstall --break-system-packages archinstall`  
4. Endi eng so‘nggi repozitoriyani klonlang: `git clone https://github.com/archlinux/archinstall`  
5. Repozitoriyaga kiring: `cd archinstall`
   *Ushbu bosqichda, masalan, `git checkout v2.3.1-rc1` bilan xususiyat branchini tanlashingiz mumkin*  
6. Manba kodini ishga tushirish uchun 2 xil variant mavjud:  
   - Maxsus branch versiyasini manbadan to‘g‘ridan-to‘g‘ri `python -m archinstall` orqali ishga tushiring; ko‘pchilik hollarda bu muammosiz ishlaydi,  
      faqat manbaga hali o‘rnatilmagan yangi bog‘liqliklar qo‘shilgan bo‘lsa, ishlamasligi mumkin  
   - Branch versiyasini `pip install --break-system-packages .` va `archinstall` orqali o‘rnating

## Live ISO tasvirisiz

Buni live ISO ishlatmasdan sinash uchun eng oson yo‘l — lokal tasvirdan foydalanish va loop qurilmasini yaratish.<br>
Buni mahalliy o‘rnatish orqali amalga oshirish mumkin: `pacman -S arch-install-scripts util-linux` va quyidagilarni bajarish:

    # truncate -s 20G testimage.img
    # losetup --partscan --show --find ./testimage.img
    # pip install --upgrade archinstall
    # python -m archinstall --script guided
    # qemu-system-x86_64 -enable-kvm -machine q35,accel=kvm -device intel-iommu -cpu host -m 4096 -boot order=d -drive file=./testimage.img,format=raw -drive if=pflash,format=raw,readonly,file=/usr/share/ovmf/x64/OVMF.4m.fd -drive if=pflash,format=raw,readonly,file=/usr/share/ovmf/x64/OVMF.4m.fd 

Bu *20 GB* hajmli `testimage.img` yaratadi va uni formatlash va o‘rnatish uchun ishlatadigan loop qurilmasini hosil qiladi.<br>
`archinstall` [yo‘riqnoma rejimida](#docs-todo) o‘rnatiladi va ishga tushiriladi. O‘rnatish tugagach, ~~test mediasini ishga tushirish uchun qemu/kvm ishlatishingiz mumkin.~~<br>
*(Aslida, test mediaidagi partition 0 ga EFI o‘zgaruvchilarini yo‘naltirish uchun bir oz EFI sehr qilish kerak bo‘ladi, shuning uchun bu to‘liq ishlamaydi, lekin sizga umumiy tasavvur beradi)*

Shuningdek, [Building and Testing](https://github.com/archlinux/archinstall/wiki/Building-and-Testing) qo‘llanmasi mavjud.<br>
U paketlash, qurish va *(qemu bilan)* installerni dev branchga qarshi ishga tushirishning hammasini bosqichma-bosqich ko‘rsatadi.


# FAQ (Tez-tez so'raladigan savollar)

## Kalitlar to‘plami muddati o‘tgan
Muammo tavsifi uchun qarang: https://archinstall.archlinux.page/help/known_issues.html#keyring-is-out-of-date-2213 va muhokama uchun: https://github.com/archlinux/archinstall/issues/2213.

Tezkor yechim uchun quyidagi buyruq eng so‘nggi kalitlar to‘plamini o‘rnatadi

```pacman -Sy archlinux-keyring```

## Windows bilan dual boot qilish

Mavjud Windows o‘rnatilgan tizim yoniga Arch Linux ni `archinstall` yordamida o‘rnatish uchun quyidagi qadamlarni bajaring:

1. Windows o‘rnatilgandan so‘ng Linux o‘rnatish uchun ajratilmagan bo‘sh joy mavjudligiga ishonch hosil qiling.  
2. ISO dan yuklab, `archinstall` ni ishga tushiring.
3. `Disk configuration` -> `Manual partitioning` ni tanlang.  
4. Windows o‘rnatilgan diskni tanlang.
5. `Create a new partition` ni tanlang.  
6. Fayl tizimi turini tanlang.  
7. Yangi bo‘lim joylashuvi uchun boshlanish va tugash sektorlarini aniqlang (qiymatlar turli birliklar bilan ko‘rsatilishi mumkin).
8. Yangi bo‘limga mountpoint `/` ni belgilang.  
9. `Boot/ESP` bo‘limiga partition menyusidan mountpoint `/boot` ni belgilang.  
10. Sozlamalaringizni tasdiqlang va asosiy menyuga qaytish uchun `Confirm and exit` ni tanlang.  
11. Zarur bo‘lsa, o‘rnatish uchun qo‘shimcha sozlamalarni o‘zgartiring.  
12. Sozlamalar tugagach, o‘rnatishni boshlang.


# Vazifa bayonoti

Archinstall foydalanuvchilarga [qo'llanma bilan o'rnatish](https://github.com/archlinux/archinstall/blob/master/archinstall/scripts/guided.py) imkonini beruvchi o'rnatuvchini taqdim etadi va u [Arch Linux prinsiplari](https://wiki.archlinux.org/index.php/Arch_Linux#Principles) ga amal qiladi, shuningdek xizmatlar, paketlar va boshqa Arch Linux elementlarini boshqarish uchun kutubxonani ham taqdim etadi.

Qo'llanma bilan o'rnatuvchi foydalanuvchi uchun qulay tajribani ta'minlaydi, jarayon davomida ixtiyoriy tanlovlarni taklif qiladi. Uning moslashuvchan tabiati shuni ta'kidlaydiki, bu tanlovlar majburiy emas.  
Bundan tashqari, qo'llanma bilan o'rnatuvchidan foydalanish qarori butunlay foydalanuvchiga tegishli bo'lib, Linux falsafasidagi to'liq erkinlik va moslashuvchanlikni ta'minlash g'oyasini aks ettiradi.

---

Archinstall asosan Arch Linux tizimidagi xizmatlar, paketlar va boshqa elementlarni boshqarish uchun moslashuvchan kutubxona sifatida ishlaydi.  
Ushbu asosiy kutubxona Archinstall tomonidan taqdim etilgan qo'llanma bilan o'rnatuvchining poydevorini tashkil qiladi. Shuningdek, u o'zlarining maxsus o'rnatish skriptlarini yaratmoqchi bo'lgan foydalanuvchilar tomonidan ishlatilishi uchun mo'ljallangan.

Shuning uchun, Archinstall iloji boricha tizimni buzadigan o'zgarishlarni kiritmaslikka harakat qiladi, faqat katta relizlarda, foydalanuvchilarga oldindan xabar berilgan holda, orqaga moslikni buzishi mumkin bo'lgan o'zgarishlar bo'lishi mumkin.

# Hissa qo'shish

Iltimos, qarang: [CONTRIBUTING.md](https://github.com/archlinux/archinstall/blob/master/CONTRIBUTING.md)
