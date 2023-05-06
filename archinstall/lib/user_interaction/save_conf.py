from __future__ import annotations

import logging
import readline

from pathlib import Path
from typing import Any, Dict, TYPE_CHECKING

from ..configuration import ConfigurationOutput
from ..menu import Menu
from ..menu.menu import MenuSelectionType
from ..output import log

if TYPE_CHECKING:
    _: Any


def save_config(config: Dict):
    def preview(selection: str):
        if options["user_config"] == selection:
            serialized = config_output.user_config_to_json()
            return f"{config_output.user_configuration_file}\n{serialized}"
        elif options["user_creds"] == selection:
            if maybe_serial := config_output.user_credentials_to_json():
                return f"{config_output.user_credentials_file}\n{maybe_serial}"
            else:
                return str(_("No configuration"))
        elif options["all"] == selection:
            output = f"{config_output.user_configuration_file}\n"
            if config_output.user_credentials_to_json():
                output += f"{config_output.user_credentials_file}\n"
            return output[:-1]
        return None

    try:
        config_output = ConfigurationOutput(config)

        options = {
            "user_config": str(_("Save user configuration (including disk layout)")),
            "user_creds": str(_("Save user credentials")),
            "all": str(_("Save all")),
        }

        save_choice = Menu(
            _("Choose which configuration to save"),
            list(options.values()),
            sort=False,
            skip=True,
            preview_size=0.75,
            preview_command=preview,
        ).run()

        if save_choice.type_ == MenuSelectionType.Skip:
            return

        readline.set_completer_delims("\t\n=")
        readline.parse_and_bind("tab: complete")
        while True:
            path = input(
                _(
                    "Enter a directory for the configuration(s) to be saved (tab completion enabled)\nSave directory: "
                )
            ).strip(" ")
            dest_path = Path(path)
            if dest_path.exists() and dest_path.is_dir():
                break
            log(_("Not a valid directory: {}").format(dest_path), fg="red")

        if not path:
            return

        prompt = _(
            "Do you want to save {} configuration file(s) in the following location?\n\n{}"
        ).format(
            list(options.keys())[list(options.values()).index(save_choice.value)],
            dest_path.absolute(),
        )
        save_confirmation = Menu(prompt, Menu.yes_no(), default_option=Menu.yes()).run()
        if save_confirmation == Menu.no():
            return

        log(
            _("Saving {} configuration files to {}").format(
                list(options.keys())[list(options.values()).index(save_choice.value)],
                dest_path.absolute(),
            ),
            level=logging.DEBUG,
        )

        if options["user_config"] == save_choice.value:
            config_output.save_user_config(dest_path)
        elif options["user_creds"] == save_choice.value:
            config_output.save_user_creds(dest_path)
        elif options["all"] == save_choice.value:
            config_output.save_user_config(dest_path)
            config_output.save_user_creds(dest_path)
    except KeyboardInterrupt:
        return