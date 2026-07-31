from pathlib import Path
from typing import assert_never, override
from archinstall.lib.models.device import BtrfsCompression, SubvolumeModification
from archinstall.lib.menu.helpers import Input, Selection
from archinstall.lib.menu.list_manager import ListManager
from archinstall.lib.menu.util import prompt_dir
from archinstall.lib.translationhandler import tr
from archinstall.tui.menu_item import MenuItem, MenuItemGroup
from archinstall.tui.result import ResultType


class SubvolumeMenu(ListManager[SubvolumeModification]):
	def __init__(
        self,
        btrfs_subvols: list[SubvolumeModification],
        prompt: str | None = None,
    ):
        self._actions = [
            tr('Add subvolume'),
            tr('Edit subvolume'),
            tr('Delete subvolume'),
        ]

        super().__init__(
            btrfs_subvols,
            [self._actions[0]],
            self._actions[1:],
            prompt,
        )

    async def show(self) -> list[SubvolumeModification] | None:
        return await super()._run()

    @override
    def selected_action_display(self, selection: SubvolumeModification) -> str:
        base = str(selection.name)
        if selection.compression != BtrfsCompression.ZSTD_3:
            base += f" [{selection.compression.value}]"
        return base

    async def _add_subvolume(self, preset: SubvolumeModification | None = None) -> SubvolumeModification | None:
        def validate(value: str | None) -> str | None:
            if value:
                return None
            return tr('Value cannot be empty')

        result = await Input(
            header=tr('Enter subvolume name'),
            allow_skip=True,
            default_value=str(preset.name) if preset else None,
            validator_callback=validate,
        ).show()

        match result.type_:
            case ResultType.Skip:
                return preset
            case ResultType.Selection:
                name = result.get_value()
            case ResultType.Reset:
                raise ValueError('Unhandled result type')
            case _:
                assert_never(result.type_)

        header = f'{tr("Subvolume name")}: {name}\n\n'
        header += tr('Enter subvolume mountpoint')

        path = await prompt_dir(
            header=header,
            allow_skip=True,
            validate=True,
            must_exist=False,
        )

        if not path:
            return preset

        default_compression = preset.compression if preset else BtrfsCompression.ZSTD_3
        compression = await self._select_compression(default_compression)

        if compression is None:
            if preset:
                return preset
            compression = BtrfsCompression.ZSTD_3

        return SubvolumeModification(
            Path(name),
            path,
            compression
        )
    async def _select_compression(self, default: BtrfsCompression) -> BtrfsCompression | None:
        header = tr('Select compression algorithm for this subvolume') + '\n\n'
        header += tr('Higher compression levels save more space but are slower') + '\n'
        header += tr('ZSTD is generally recommended for most use cases') + '\n\n'
        header += tr('Selection') + ':'

        items = []
        for display_name, comp_value in BtrfsCompression.get_ui_options():
            label = display_name
            if comp_value == default:
                label = f"* {label} (default)"
            items.append(MenuItem(label, value=comp_value))

        group = MenuItemGroup(items, sort_items=False)

        result = await Selection[BtrfsCompression](
            group,
            header=header,
            allow_skip=True,
        ).show()

        match result.type_:
            case ResultType.Selection:
                return result.get_value()
            case ResultType.Skip:
                return default
            case _:
                return None

    @override
    async def handle_action(
        self,
        action: str,
        entry: SubvolumeModification | None,
        data: list[SubvolumeModification],
    ) -> list[SubvolumeModification]:
        if action == self._actions[0]:
            new_subvolume = await self._add_subvolume()

            if new_subvolume is not None:
                data = [d for d in data if d.name != new_subvolume.name]
                data += [new_subvolume]
        elif entry is not None:
            if action == self._actions[1]:
                new_subvolume = await self._add_subvolume(entry)

                if new_subvolume is not None:
                    data = [d for d in data if d.name != entry.name and d.name != new_subvolume.name]
                    data += [new_subvolume]
            elif action == self._actions[2]:
                data = [d for d in data if d != entry]

        return data
