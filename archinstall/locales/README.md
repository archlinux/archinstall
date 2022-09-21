# Nationalization

Archinstall supports multiple languages, which depend on translations coming from the community :)

## Important Note
Before starting a new language translation be aware that a font for that language may not be
available on the ISO. We are using the pre-installed font `/usr/share/kbd/consolefonts/LatGrkCyr-8x16.psfu.gz` in archinstall
which should cover a fair amount of different languages but unfortunately not all of them.

We have the option to provide a custom font in case the above is not covering a specific language, which can
be achieved by installing the font yourself on the ISO and saving it to `/usr/share/kbd/consolefonts/archinstall_font.psfu.gz`.
If this font is present it will be automatically loaded and all languages which are not supported by the default font will
be enabled (but only some might actually work).

Please make sure that the provided language works with the default font on the ISO, and if not mark it in the `languages.json`
that it needs an external dependency
```
{"abbr": "ur", "lang": "Urdu", "translated_lang": "اردو", "external_dep":  true},
```

## Adding new languages

New languages can be added simply by creating a new folder with the proper language abbreviation (see list `languages.json` if unsure).  
Run the following command to create a new template for a language
```
mkdir -p <abbr>/LC_MESSAGES/ && touch <abbr>/LC_MESSAGES/base.po
```

After that run the script `./locales_generator.sh` it will automatically populate the new `base.po` file with the strings that 
need to be translated into the new language.  
For example the `base.po` might contain something like the following now 
```
#: lib/user_interaction.py:82
msgid "Do you really want to abort?"
msgstr ""
```

The `msgid` is the identifier of the string in the code as well as the default text to be displayed, meaning that if no
translation is provided for a language then this is the text that is going to be shown. 

To perform translations for a language this file can be edited manually or the neat `poedit` can be used (https://poedit.net/).
If editing the file manually, write the translation in the `msgstr` part

```
#: lib/user_interaction.py:82
msgid "Do you really want to abort?"
msgstr "Wollen sie wirklich abbrechen?"
```

After the translations have been written, run the script once more `./locales_generator.sh` and it will auto-generate the `base.mo` file with the included translations.
After that you're all ready to go and enjoy Archinstall in the new language :)

To display the language inside Archinstall in your own tongue, please edit the file `languages.json` and 
add a `translated_lang` entry to the respective language, e.g. 

```
 {"abbr": "pl", "lang": "Polish", "translated_lang": "Polskie"}
```
