# Nationalization

Archinstall supports multiple languages, which depend on translations coming from the community :) 

New languages can be added simply by creating a new folder with the proper language abbrevation (see list `languages.json` if unsure).  
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
