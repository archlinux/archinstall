<!-- <div align="center"> -->
<img src="https://github.com/archlinux/archinstall/raw/master/docs/logo.png" alt="drawing" width="200"/>

<!-- Language Switcher -->
[🇬🇧 English](README.md) | [🇷🇺 Русский](README.ru.md) | [🇺🇿 O'zbekcha](README.uz.md)

<!-- </div> -->
# Arch Installer
[![Lint Python and Find Syntax Errors](https://github.com/archlinux/archinstall/actions/workflows/flake8.yaml/badge.svg)](https://github.com/archlinux/archinstall/actions/workflows/flake8.yaml)

Простой и удобный [установщик Arch Linux](https://wiki.archlinux.org/index.php/Arch_Linux) с дополнительными возможностями.  
Установщик также может использоваться как **Python-библиотека** для установки Arch Linux и управления сервисами, пакетами и другими элементами внутри установленной системы *(обычно из live-среды)*.

* archinstall [discord](https://discord.gg/aDeMffrxNg) сервер
* archinstall [#archinstall:matrix.org](https://matrix.to/#/#archinstall:matrix.org) канал Matrix
* archinstall [#archinstall@irc.libera.chat:6697](https://web.libera.chat/?channel=#archinstall)
* archinstall [документация](https://archinstall.archlinux.page/)

# Установка и использование
```shell
sudo pacman -S archinstall

Альтернативные способы установки: клонировать репозиторий через `git clone` или использовать `pip install --upgrade archinstall`.

## Запуск [навигационного](https://github.com/archlinux/archinstall/blob/master/archinstall/scripts/guided.py) установщика

Если вы используете Arch Linux live-ISO или установили через `pip`:
```shell
archinstall
```

## Запуск [навигационного](https://github.com/archlinux/archinstall/blob/master/archinstall/scripts/guided.py) установщика через `git`

```shell
# cd archinstall-git
# python -m archinstall
```

#### Дополнительно
Некоторые дополнительные параметры, которые большинству пользователей не нужны, скрыты за флагом `--advanced`.

## Запуск из конфигурационного файла или по URL

`archinstall` можно запускать с использованием JSON-конфигурационного файла. Существует два разных файла конфигурации:  
`user_configuration.json` содержит все общие параметры установки, тогда как `user_credentials.json`  
содержит чувствительные данные пользователя, такие как пароль пользователя, пароль root и пароль для шифрования.

Пример файла конфигурации пользователя можно найти здесь:  
[configuration file](https://github.com/archlinux/archinstall/blob/master/examples/config-sample.json)  
А пример файла с учетными данными здесь:  
[credentials file](https://github.com/archlinux/archinstall/blob/master/examples/creds-sample.json).

**Совет:** Файлы конфигурации можно сгенерировать автоматически, запустив `archinstall`, настроив все необходимые пункты меню и выбрав `Save configuration`.

Чтобы загрузить конфигурационный файл в `archinstall`, выполните следующую команду:
```shell
archinstall --config <путь к файлу конфигурации пользователя или URL> --creds <путь к файлу с учетными данными пользователя или URL>
```

### Шифрование файла с учетными данными
По умолчанию все учетные данные пользователей хэшируются с помощью `yescrypt`, и только хэш сохраняется в файле `user_credentials.json`.  
Это невозможно для пароля шифрования диска, который должен храниться в открытом виде, чтобы его можно было применить.

Однако при выборе сохранения файлов конфигурации `archinstall` предложит зашифровать содержимое файла `user_credentials.json`.  
Появится запрос на ввод пароля для шифрования файла.  

При передаче зашифрованного `user_configuration.json` в качестве аргумента с `--creds <user_credentials.json>`  
существует несколько способов предоставить ключ для расшифровки:
* Передать ключ расшифровки через аргумент командной строки `--creds-decryption-key <password>`
* Сохранить ключ шифрования в переменной окружения `ARCHINSTALL_CREDS_DECRYPTION_KEY`, которая будет считана автоматически
* Если ни один из вышеуказанных способов не использован, появится запрос на ручной ввод ключа расшифровки


# Помощь и решение проблем

Если вы столкнулись с какой-либо проблемой, пожалуйста, создайте issue на GitHub или задайте вопрос в канале помощи [discord](https://discord.gg/aDeMffrxNg).

При создании issue, пожалуйста:  
* Укажите stacktrace вывода, если применимо  
* Приложите файл `/var/log/archinstall/install.log` к тикету. Это поможет нам быстрее вам помочь!  
  * Чтобы извлечь лог из ISO-образа, можно использовать:<br>
    ```shell
    curl -F'file=@/var/log/archinstall/install.log' https://0x0.st
    ```


# Доступные языки

Archinstall доступен на нескольких языках, которые были добавлены и поддерживаются сообществом.  
Язык можно выбрать прямо в установщике (первый пункт меню). Учтите, что не все языки имеют полный перевод, так как мы полагаемся на вклад участников.  
Каждый язык имеет индикатор, показывающий, насколько он переведен.

Любой вклад в переводы приветствуется.  
Чтобы начать, пожалуйста, следуйте [инструкции](https://github.com/archlinux/archinstall/blob/master/archinstall/locales/README.md).

## Шрифты
ISO-образ не содержит всех шрифтов, необходимых для разных языков.  
Шрифты, использующие отличные от латинских символы, будут отображаться некорректно.  
Если вы хотите использовать такие языки, соответствующий шрифт нужно установить вручную в консоли.

Все доступные консольные шрифты находятся в `/usr/share/kbd/consolefonts` и устанавливаются командой `setfont LatGrkCyr-8x16`.


# Создание собственного скрипта установки

## Скриптирование интерактивной установки

Для примера полностью скриптируемой интерактивной установки, пожалуйста, смотрите пример:  
[interactive_installation.py](https://github.com/archlinux/archinstall/blob/master/archinstall/scripts/guided.py)


> **Чтобы создать собственный ISO с этим скриптом:** следуйте инструкции [ArchISO](https://wiki.archlinux.org/index.php/archiso) по созданию собственного ISO.

## Скриптирование полностью автоматизированной установки

Для примера полностью скриптируемой автоматизированной установки, пожалуйста, смотрите пример:  
[full_automated_installation.py](https://github.com/archlinux/archinstall/blob/master/examples/full_automated_installation.py)

# Профили

`archinstall` поставляется с набором преднастроенных профилей, доступных для выбора во время процесса установки.

- [Рабочий стол](https://github.com/archlinux/archinstall/tree/master/archinstall/default_profiles/desktops)
- [Сервер](https://github.com/archlinux/archinstall/tree/master/archinstall/default_profiles/servers)

Определения профилей и пакеты, которые они устанавливают, можно просмотреть прямо в меню или здесь:  
[default profiles](https://github.com/archlinux/archinstall/tree/master/archinstall/default_profiles)


# Тестирование

## Использование Live ISO-образа

Если вы хотите протестировать коммит, ветку или самую свежую версию из репозитория, используя стандартный Live ISO-образ Arch Linux,  
замените версию `archinstall` на более новую и выполните следующие шаги.

*Примечание: При загрузке с Live USB, пространство на ramdisk ограничено и может быть недостаточным для повторной установки или обновления установщика.  
В случае возникновения этой проблемы можно использовать следующие варианты:  
- Изменить размер корневого раздела https://wiki.archlinux.org/title/Archiso#Adjusting_the_size_of_the_root_file_system  
- Указать параметр загрузки `copytoram=y` (https://gitlab.archlinux.org/archlinux/mkinitcpio/mkinitcpio-archiso/-/blob/master/docs/README.bootparams#L26), который скопирует корневую файловую систему в tmpfs.*

1. Вам нужно рабочее сетевое соединение  
2. Установите необходимые пакеты для сборки с помощью `pacman -Sy; pacman -S git python-pip gcc pkgconf`  
   *(обратите внимание, что это может не сработать в зависимости от объема вашей оперативной памяти и текущего состояния свободного места в squashfs)*  
3. Удалите предыдущую версию archinstall с помощью `pip uninstall --break-system-packages archinstall`
4. Теперь клонируйте последний репозиторий с помощью `git clone https://github.com/archlinux/archinstall`  
5. Перейдите в репозиторий с помощью `cd archinstall`  
   *На этом этапе вы можете, например, переключиться на нужную ветку с `git checkout v2.3.1-rc1`*  
6. Чтобы запустить исходный код, есть два варианта:  
   - Запустить конкретную версию ветки напрямую из исходников с помощью `python -m archinstall`. В большинстве случаев это работает нормально, исключение — если в исходниках появились новые зависимости, которые ещё не установлены  
   - Установить версию ветки с помощью `pip install --break-system-packages .` и затем использовать `archinstall`

## Без использования Live ISO-образа

Чтобы протестировать это без Live ISO, самым простым способом является использование локального образа и создание loop-устройства.<br>
Это можно сделать, установив локально `pacman -S arch-install-scripts util-linux` и выполнив следующие действия:

    # truncate -s 20G testimage.img
    # losetup --partscan --show --find ./testimage.img
    # pip install --upgrade archinstall
    # python -m archinstall --script guided
    # qemu-system-x86_64 -enable-kvm -machine q35,accel=kvm -device intel-iommu -cpu host -m 4096 -boot order=d -drive file=./testimage.img,format=raw -drive if=pflash,format=raw,readonly,file=/usr/share/ovmf/x64/OVMF.4m.fd -drive if=pflash,format=raw,readonly,file=/usr/share/ovmf/x64/OVMF.4m.fd 

Это создаст *20 ГБ* `testimage.img` и loop-устройство, которое можно использовать для форматирования и установки.  
`archinstall` будет установлен и выполнен в [guided режиме](#docs-todo). После завершения установки, ~~вы можете использовать qemu/kvm для загрузки тестового образа.~~  
*(На самом деле потребуется сделать некоторые действия с EFI, чтобы указать переменные EFI на раздел 0 в тестовом образе, поэтому это не будет работать "из коробки", но даёт общее представление о том, что мы пытаемся сделать)*

Также есть руководство по [Сборке и тестированию](https://github.com/archlinux/archinstall/wiki/Building-and-Testing).<br>
Оно охватывает весь процесс — от упаковки, сборки и запуска *(с помощью qemu)* установщика для dev-ветки.


# FAQ (Часто задаваемые вопросы)

## Устаревший ключевой набор
Описание проблемы см. на https://archinstall.archlinux.page/help/known_issues.html#keyring-is-out-of-date-2213 и обсуждение в issue https://github.com/archlinux/archinstall/issues/2213.

Для быстрого решения этой проблемы выполните следующую команду для установки последних ключей:

```pacman -Sy archlinux-keyring```

## Как установить Arch Linux вместе с Windows (Dual Boot)

Чтобы установить Arch Linux рядом с уже существующей установкой Windows с помощью `archinstall`, выполните следующие шаги:

1. Убедитесь, что после установки Windows есть нераспределённое пространство для установки Linux.  
2. Загрузитесь с ISO и запустите `archinstall`.  
3. Выберите `Disk configuration` -> `Manual partitioning`.  
4. Выберите диск, на котором установлена Windows.  
5. Выберите `Create a new partition`.
6. Выберите тип файловой системы.  
7. Укажите начальный и конечный сектора для нового раздела (значения могут иметь различные единицы измерения).  
8. Назначьте точку монтирования `/` для нового раздела.  
9. Назначьте раздел `Boot/ESP` точкой монтирования `/boot` через меню разметки.
10. Подтвердите настройки и вернитесь в главное меню, выбрав `Confirm and exit`.  
11. При необходимости измените дополнительные параметры установки.  
12. Запустите установку после завершения настройки.


# Цель проекта

Archinstall предлагает [руководимый установщик](https://github.com/archlinux/archinstall/blob/master/archinstall/scripts/guided.py), который следует  
[принципам Arch Linux](https://wiki.archlinux.org/index.php/Arch_Linux#Principles), а также библиотеку для управления сервисами, пакетами и другими аспектами Arch Linux.

Руководимый установщик обеспечивает удобство для пользователя, предлагая выбор опций на протяжении всего процесса. Подчеркивая гибкость, эти опции никогда не являются обязательными.  
Кроме того, решение использовать руководимый установщик полностью остаётся за пользователем, что отражает философию Linux — предоставление полной свободы и гибкости.

---

Archinstall в первую очередь функционирует как гибкая библиотека для управления сервисами, пакетами и другими компонентами системы Arch Linux.  
Эта основная библиотека является фундаментом для руководимого установщика, предоставляемого Archinstall. Она также предназначена для тех, кто хочет создавать свои собственные скрипты установки.

Поэтому Archinstall будет стараться не вносить критических изменений, за исключением крупных релизов, которые могут нарушить обратную совместимость после уведомления о таких изменениях.


# Вклад в проект

Пожалуйста, смотрите [CONTRIBUTING.md](https://github.com/archlinux/archinstall/blob/master/CONTRIBUTING.md)
