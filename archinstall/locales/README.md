# Nationalization

Archinstall supports multiple languages, which depend on translations coming from the community :)

## Important Note
Before starting a new language translation be aware that a font for that language may not be
available on the ISO.

Fonts that are using a different character set than Latin will not be displayed correctly. If those languages
want to be selected, then a proper font has to be set manually in the console.

All available console fonts can be found in `/usr/share/kbd/consolefonts` and they
can be set with `setfont LatGrkCyr-8x16`.

Also note that for example [grub bootloader](https://www.gnu.org/software/grub/manual/grub/grub.html#Input-terminal) has ASCII limited range:
For full disk encryption (LUKS2) or grub-shell, boot options edit: this means alphanumeric latin characters (one-char-per-keystroke).

Archinstall validates this by making sure your passwords are ASCII compatible.
It is quite trivial through Login-manager and/or Desktop Environment to set other layouts or switching later-on.

For full `at_keyboard` support it is possible through `ckbcomp` See guide [here](https://fitzcarraldoblog.wordpress.com/2019/04/21/how-to-change-the-keymap-keyboard-layout-used-by-the-grub-shell-in-gentoo-linux/) And [ckbcomp<sup>AUR</sup>](https://aur.archlinux.org/packages/ckbcomp)

By default bootloaders look for `vconsole.conf` keymap. Other bootloaders such as `systemd-boot` and `limine` have full keymap support.

## Adding new languages

New languages can be added simply by creating a new folder with the proper language abbreviation (see list `languages.json` if unsure).
Run the following command to create a new template for a language
```
mkdir -p <abbr>/LC_MESSAGES/ && touch <abbr>/LC_MESSAGES/base.po
```

After that run the script `./locales_generator.sh <lang_abbr>` it will automatically populate the new `base.po` file with the strings that
need to be translated into the new language.
For example the `base.po` might contain something like the following now
```
#: lib/user_interaction.py:82
msgid "Do you really want to abort?"
msgstr ""
```

The `msgid` is the identifier of the string in the code as well as the default text to be displayed, meaning that if no
translation is provided for a language then this is the text that is going to be shown.

## Perform translations

Firstly run the script `./locales_generator.sh <lang_abbr>` to update `base.po` to the latest.

To perform translations for a language, the file `base.po` can be edited manually, or the neat `poedit` can be used (https://poedit.net/).
If editing the file manually, write the translation in the `msgstr` part

```
#: lib/user_interaction.py:82
msgid "Do you really want to abort?"
msgstr "Wollen sie wirklich abbrechen?"
```

After the translations have been written, run the script once more `./locales_generator.sh <lang_abbr>` and it will auto-generate the `base.mo` file with the included translations.

After that you're all ready to go and enjoy Archinstall in the new language :)
