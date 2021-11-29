"""
This file is copied over from the simple-term-menu project
(https://github.com/IngoMeyer441/simple-term-menu)
In order to comply with installation methods of Arch Linux.
We here by copy the MIT license attached to the project at the time of copy:

Copyright 2021 Forschungszentrum Jülich GmbH

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
the Software, and to permit persons to whom the Software is furnished to do so,
subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""
import argparse
import copy
import ctypes
import io
import locale
import os
import platform
import re
import shlex
import signal
import string
import subprocess
import sys
from locale import getlocale
from types import FrameType
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    Iterator,
    List,
    Match,
    Optional,
    Pattern,
    Sequence,
    Set,
    TextIO,
    Tuple,
    Union,
    cast,
)

try:
    import termios
except ImportError as e:
    raise NotImplementedError('"{}" is currently not supported.'.format(platform.system())) from e


__author__ = "Ingo Meyer"
__email__ = "i.meyer@fz-juelich.de"
__copyright__ = "Copyright © 2021 Forschungszentrum Jülich GmbH. All rights reserved."
__license__ = "MIT"
__version_info__ = (1, 4, 1)
__version__ = ".".join(map(str, __version_info__))


DEFAULT_ACCEPT_KEYS = ("enter",)
DEFAULT_CLEAR_MENU_ON_EXIT = True
DEFAULT_CLEAR_SCREEN = False
DEFAULT_CYCLE_CURSOR = True
DEFAULT_EXIT_ON_SHORTCUT = True
DEFAULT_MENU_CURSOR = "> "
DEFAULT_MENU_CURSOR_STYLE = ("fg_red", "bold")
DEFAULT_MENU_HIGHLIGHT_STYLE = ("standout",)
DEFAULT_MULTI_SELECT = False
DEFAULT_MULTI_SELECT_CURSOR = "[*] "
DEFAULT_MULTI_SELECT_CURSOR_BRACKETS_STYLE = ("fg_gray",)
DEFAULT_MULTI_SELECT_CURSOR_STYLE = ("fg_yellow", "bold")
DEFAULT_MULTI_SELECT_KEYS = (" ", "tab")
DEFAULT_MULTI_SELECT_SELECT_ON_ACCEPT = True
DEFAULT_PREVIEW_BORDER = True
DEFAULT_PREVIEW_SIZE = 0.25
DEFAULT_PREVIEW_TITLE = "preview"
DEFAULT_SEARCH_CASE_SENSITIVE = False
DEFAULT_SEARCH_HIGHLIGHT_STYLE = ("fg_black", "bg_yellow", "bold")
DEFAULT_SEARCH_KEY = "/"
DEFAULT_SHORTCUT_BRACKETS_HIGHLIGHT_STYLE = ("fg_gray",)
DEFAULT_SHORTCUT_KEY_HIGHLIGHT_STYLE = ("fg_blue",)
DEFAULT_SHOW_MULTI_SELECT_HINT = False
DEFAULT_SHOW_SEARCH_HINT = False
DEFAULT_SHOW_SHORTCUT_HINTS = False
DEFAULT_SHOW_SHORTCUT_HINTS_IN_STATUS_BAR = True
DEFAULT_STATUS_BAR_BELOW_PREVIEW = False
DEFAULT_STATUS_BAR_STYLE = ("fg_yellow", "bg_black")
MIN_VISIBLE_MENU_ENTRIES_COUNT = 3


class InvalidParameterCombinationError(Exception):
    pass


class InvalidStyleError(Exception):
    pass


class NoMenuEntriesError(Exception):
    pass


class PreviewCommandFailedError(Exception):
    pass


class UnknownMenuEntryError(Exception):
    pass


def get_locale() -> str:
    user_locale = locale.getlocale()[1]
    if user_locale is None:
        return "ascii"
    else:
        return user_locale.lower()


def wcswidth(text: str) -> int:
    if not hasattr(wcswidth, "libc"):
        if platform.system() == "Darwin":
            wcswidth.libc = ctypes.cdll.LoadLibrary("libSystem.dylib")  # type: ignore
        else:
            wcswidth.libc = ctypes.cdll.LoadLibrary("libc.so.6")  # type: ignore
    user_locale = get_locale()
    # First replace any null characters with the unicode replacement character (U+FFFD) since they cannot be passed
    # in a `c_wchar_p`
    encoded_text = text.replace("\0", "\uFFFD").encode(encoding=user_locale, errors="replace")
    return wcswidth.libc.wcswidth(  # type: ignore
        ctypes.c_wchar_p(encoded_text.decode(encoding=user_locale)), len(encoded_text)
    )


def static_variables(**variables: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(f: Callable[..., Any]) -> Callable[..., Any]:
        for key, value in variables.items():
            setattr(f, key, value)
        return f

    return decorator


class BoxDrawingCharacters:
    if getlocale()[1] == "UTF-8":
        # Unicode box characters
        horizontal = "─"
        vertical = "│"
        upper_left = "┌"
        upper_right = "┐"
        lower_left = "└"
        lower_right = "┘"
    else:
        # ASCII box characters
        horizontal = "-"
        vertical = "|"
        upper_left = "+"
        upper_right = "+"
        lower_left = "+"
        lower_right = "+"


class TerminalMenu:
    class Search:
        def __init__(
            self,
            menu_entries: Iterable[str],
            search_text: Optional[str] = None,
            case_senitive: bool = False,
            show_search_hint: bool = False,
        ):
            self._menu_entries = menu_entries
            self._case_sensitive = case_senitive
            self._show_search_hint = show_search_hint
            self._matches = []  # type: List[Tuple[int, Match[str]]]
            self._search_regex = None  # type: Optional[Pattern[str]]
            self._change_callback = None  # type: Optional[Callable[[], None]]
            # Use the property setter since it has some more logic
            self.search_text = search_text

        def _update_matches(self) -> None:
            if self._search_regex is None:
                self._matches = []
            else:
                matches = []
                for i, menu_entry in enumerate(self._menu_entries):
                    match_obj = self._search_regex.search(menu_entry)
                    if match_obj:
                        matches.append((i, match_obj))
                self._matches = matches

        @property
        def matches(self) -> List[Tuple[int, Match[str]]]:
            return list(self._matches)

        @property
        def search_regex(self) -> Optional[Pattern[str]]:
            return self._search_regex

        @property
        def search_text(self) -> Optional[str]:
            return self._search_text

        @search_text.setter
        def search_text(self, text: Optional[str]) -> None:
            self._search_text = text
            search_text = self._search_text
            self._search_regex = None
            while search_text and self._search_regex is None:
                try:
                    self._search_regex = re.compile(search_text, flags=re.IGNORECASE if not self._case_sensitive else 0)
                except re.error:
                    search_text = search_text[:-1]
            self._update_matches()
            if self._change_callback:
                self._change_callback()

        @property
        def change_callback(self) -> Optional[Callable[[], None]]:
            return self._change_callback

        @change_callback.setter
        def change_callback(self, callback: Optional[Callable[[], None]]) -> None:
            self._change_callback = callback

        @property
        def occupied_lines_count(self) -> int:
            if not self and not self._show_search_hint:
                return 0
            else:
                return 1

        def __bool__(self) -> bool:
            return self._search_text is not None

        def __contains__(self, menu_index: int) -> bool:
            return any(i == menu_index for i, _ in self._matches)

        def __len__(self) -> int:
            return wcswidth(self._search_text) if self._search_text is not None else 0

    class Selection:
        def __init__(self, num_menu_entries: int, preselected_indices: Optional[Iterable[int]] = None):
            self._num_menu_entries = num_menu_entries
            self._selected_menu_indices = set(preselected_indices) if preselected_indices is not None else set()

        def clear(self) -> None:
            self._selected_menu_indices.clear()

        def add(self, menu_index: int) -> None:
            self[menu_index] = True

        def remove(self, menu_index: int) -> None:
            self[menu_index] = False

        def toggle(self, menu_index: int) -> bool:
            self[menu_index] = menu_index not in self._selected_menu_indices
            return self[menu_index]

        def __bool__(self) -> bool:
            return bool(self._selected_menu_indices)

        def __contains__(self, menu_index: int) -> bool:
            return menu_index in self._selected_menu_indices

        def __getitem__(self, menu_index: int) -> bool:
            return menu_index in self._selected_menu_indices

        def __setitem__(self, menu_index: int, is_selected: bool) -> None:
            if is_selected:
                self._selected_menu_indices.add(menu_index)
            else:
                self._selected_menu_indices.remove(menu_index)

        def __iter__(self) -> Iterator[int]:
            return iter(self._selected_menu_indices)

        @property
        def selected_menu_indices(self) -> Tuple[int, ...]:
            return tuple(sorted(self._selected_menu_indices))

    class View:
        def __init__(
            self,
            menu_entries: Iterable[str],
            search: "TerminalMenu.Search",
            selection: "TerminalMenu.Selection",
            viewport: "TerminalMenu.Viewport",
            cycle_cursor: bool = True,
        ):
            self._menu_entries = list(menu_entries)
            self._search = search
            self._selection = selection
            self._viewport = viewport
            self._cycle_cursor = cycle_cursor
            self._active_displayed_index = None  # type: Optional[int]
            self.update_view()

        def update_view(self) -> None:
            if self._search and self._search.search_text != "":
                self._displayed_index_to_menu_index = tuple(i for i, match_obj in self._search.matches)
            else:
                self._displayed_index_to_menu_index = tuple(range(len(self._menu_entries)))
            self._menu_index_to_displayed_index = {
                menu_index: displayed_index
                for displayed_index, menu_index in enumerate(self._displayed_index_to_menu_index)
            }
            self._active_displayed_index = 0 if self._displayed_index_to_menu_index else None
            self._viewport.search_lines_count = self._search.occupied_lines_count
            self._viewport.keep_visible(self._active_displayed_index)

        def increment_active_index(self) -> None:
            if self._active_displayed_index is not None:
                if self._active_displayed_index + 1 < len(self._displayed_index_to_menu_index):
                    self._active_displayed_index += 1
                elif self._cycle_cursor:
                    self._active_displayed_index = 0
                self._viewport.keep_visible(self._active_displayed_index)

        def decrement_active_index(self) -> None:
            if self._active_displayed_index is not None:
                if self._active_displayed_index > 0:
                    self._active_displayed_index -= 1
                elif self._cycle_cursor:
                    self._active_displayed_index = len(self._displayed_index_to_menu_index) - 1
                self._viewport.keep_visible(self._active_displayed_index)

        def is_visible(self, menu_index: int) -> bool:
            return menu_index in self._menu_index_to_displayed_index and (
                self._viewport.lower_index
                <= self._menu_index_to_displayed_index[menu_index]
                <= self._viewport.upper_index
            )

        def convert_menu_index_to_displayed_index(self, menu_index: int) -> Optional[int]:
            if menu_index in self._menu_index_to_displayed_index:
                return self._menu_index_to_displayed_index[menu_index]
            else:
                return None

        def convert_displayed_index_to_menu_index(self, displayed_index: int) -> int:
            return self._displayed_index_to_menu_index[displayed_index]

        @property
        def active_menu_index(self) -> Optional[int]:
            if self._active_displayed_index is not None:
                return self._displayed_index_to_menu_index[self._active_displayed_index]
            else:
                return None

        @active_menu_index.setter
        def active_menu_index(self, value: int) -> None:
            self._selected_index = value
            self._active_displayed_index = [
                displayed_index
                for displayed_index, menu_index in enumerate(self._displayed_index_to_menu_index)
                if menu_index == value
            ][0]
            self._viewport.keep_visible(self._active_displayed_index)

        @property
        def active_displayed_index(self) -> Optional[int]:
            return self._active_displayed_index

        @property
        def displayed_selected_indices(self) -> List[int]:
            return [
                self._menu_index_to_displayed_index[selected_index]
                for selected_index in self._selection
                if selected_index in self._menu_index_to_displayed_index
            ]

        def __bool__(self) -> bool:
            return self._active_displayed_index is not None

        def __iter__(self) -> Iterator[Tuple[int, int, str]]:
            for displayed_index, menu_index in enumerate(self._displayed_index_to_menu_index):
                if self._viewport.lower_index <= displayed_index <= self._viewport.upper_index:
                    yield (displayed_index, menu_index, self._menu_entries[menu_index])

    class Viewport:
        def __init__(
            self,
            num_menu_entries: int,
            title_lines_count: int,
            status_bar_lines_count: int,
            preview_lines_count: int,
            search_lines_count: int,
        ):
            self._num_menu_entries = num_menu_entries
            self._title_lines_count = title_lines_count
            self._status_bar_lines_count = status_bar_lines_count
            # Use the property setter since it has some more logic
            self.preview_lines_count = preview_lines_count
            self.search_lines_count = search_lines_count
            self._num_lines = self._calculate_num_lines()
            self._viewport = (0, min(self._num_menu_entries, self._num_lines) - 1)
            self.keep_visible(cursor_position=None, refresh_terminal_size=False)

        def _calculate_num_lines(self) -> int:
            return (
                TerminalMenu._num_lines()
                - self._title_lines_count
                - self._status_bar_lines_count
                - self._preview_lines_count
                - self._search_lines_count
            )

        def keep_visible(self, cursor_position: Optional[int], refresh_terminal_size: bool = True) -> None:
            # Treat `cursor_position=None` like `cursor_position=0`
            if cursor_position is None:
                cursor_position = 0
            if refresh_terminal_size:
                self.update_terminal_size()
            if self._viewport[0] <= cursor_position <= self._viewport[1]:
                # Cursor is already visible
                return
            if cursor_position < self._viewport[0]:
                scroll_num = cursor_position - self._viewport[0]
            else:
                scroll_num = cursor_position - self._viewport[1]
            self._viewport = (self._viewport[0] + scroll_num, self._viewport[1] + scroll_num)

        def update_terminal_size(self) -> None:
            num_lines = self._calculate_num_lines()
            if num_lines != self._num_lines:
                # First let the upper index grow or shrink
                upper_index = min(num_lines, self._num_menu_entries) - 1
                # Then, use as much space as possible for the `lower_index`
                lower_index = max(0, upper_index - num_lines)
                self._viewport = (lower_index, upper_index)
                self._num_lines = num_lines

        @property
        def lower_index(self) -> int:
            return self._viewport[0]

        @property
        def upper_index(self) -> int:
            return self._viewport[1]

        @property
        def viewport(self) -> Tuple[int, int]:
            return self._viewport

        @property
        def size(self) -> int:
            return self._viewport[1] - self._viewport[0] + 1

        @property
        def num_menu_entries(self) -> int:
            return self._num_menu_entries

        @property
        def title_lines_count(self) -> int:
            return self._title_lines_count

        @property
        def status_bar_lines_count(self) -> int:
            return self._status_bar_lines_count

        @status_bar_lines_count.setter
        def status_bar_lines_count(self, value: int) -> None:
            self._status_bar_lines_count = value

        @property
        def preview_lines_count(self) -> int:
            return self._preview_lines_count

        @preview_lines_count.setter
        def preview_lines_count(self, value: int) -> None:
            self._preview_lines_count = min(
                value if value >= 3 else 0,
                TerminalMenu._num_lines()
                - self._title_lines_count
                - self._status_bar_lines_count
                - MIN_VISIBLE_MENU_ENTRIES_COUNT,
            )

        @property
        def search_lines_count(self) -> int:
            return self._search_lines_count

        @search_lines_count.setter
        def search_lines_count(self, value: int) -> None:
            self._search_lines_count = value

        @property
        def must_scroll(self) -> bool:
            return self._num_menu_entries > self._num_lines

    _codename_to_capname = {
        "bg_black": "setab 0",
        "bg_blue": "setab 4",
        "bg_cyan": "setab 6",
        "bg_gray": "setab 7",
        "bg_green": "setab 2",
        "bg_purple": "setab 5",
        "bg_red": "setab 1",
        "bg_yellow": "setab 3",
        "bold": "bold",
        "clear": "clear",
        "colors": "colors",
        "cursor_down": "cud1",
        "cursor_invisible": "civis",
        "cursor_left": "cub1",
        "cursor_right": "cuf1",
        "cursor_up": "cuu1",
        "cursor_visible": "cnorm",
        "delete_line": "dl1",
        "down": "kcud1",
        "enter_application_mode": "smkx",
        "exit_application_mode": "rmkx",
        "fg_black": "setaf 0",
        "fg_blue": "setaf 4",
        "fg_cyan": "setaf 6",
        "fg_gray": "setaf 7",
        "fg_green": "setaf 2",
        "fg_purple": "setaf 5",
        "fg_red": "setaf 1",
        "fg_yellow": "setaf 3",
        "italics": "sitm",
        "reset_attributes": "sgr0",
        "standout": "smso",
        "underline": "smul",
        "up": "kcuu1",
    }
    _name_to_control_character = {
        "backspace": "",  # Is assigned later in `self._init_backspace_control_character`
        "ctrl-j": "\012",
        "ctrl-k": "\013",
        "enter": "\015",
        "escape": "\033",
        "tab": "\t",
    }
    _codenames = tuple(_codename_to_capname.keys())
    _codename_to_terminal_code = None  # type: Optional[Dict[str, str]]
    _terminal_code_to_codename = None  # type: Optional[Dict[str, str]]

    def __init__(
        self,
        menu_entries: Iterable[str],
        *,
        accept_keys: Iterable[str] = DEFAULT_ACCEPT_KEYS,
        clear_menu_on_exit: bool = DEFAULT_CLEAR_MENU_ON_EXIT,
        clear_screen: bool = DEFAULT_CLEAR_SCREEN,
        cursor_index: Optional[int] = None,
        cycle_cursor: bool = DEFAULT_CYCLE_CURSOR,
        exit_on_shortcut: bool = DEFAULT_EXIT_ON_SHORTCUT,
        menu_cursor: Optional[str] = DEFAULT_MENU_CURSOR,
        menu_cursor_style: Optional[Iterable[str]] = DEFAULT_MENU_CURSOR_STYLE,
        menu_highlight_style: Optional[Iterable[str]] = DEFAULT_MENU_HIGHLIGHT_STYLE,
        multi_select: bool = DEFAULT_MULTI_SELECT,
        multi_select_cursor: str = DEFAULT_MULTI_SELECT_CURSOR,
        multi_select_cursor_brackets_style: Optional[Iterable[str]] = DEFAULT_MULTI_SELECT_CURSOR_BRACKETS_STYLE,
        multi_select_cursor_style: Optional[Iterable[str]] = DEFAULT_MULTI_SELECT_CURSOR_STYLE,
        multi_select_empty_ok: bool = False,
        multi_select_keys: Optional[Iterable[str]] = DEFAULT_MULTI_SELECT_KEYS,
        multi_select_select_on_accept: bool = DEFAULT_MULTI_SELECT_SELECT_ON_ACCEPT,
        preselected_entries: Optional[Iterable[Union[str, int]]] = None,
        preview_border: bool = DEFAULT_PREVIEW_BORDER,
        preview_command: Optional[Union[str, Callable[[str], str]]] = None,
        preview_size: float = DEFAULT_PREVIEW_SIZE,
        preview_title: str = DEFAULT_PREVIEW_TITLE,
        search_case_sensitive: bool = DEFAULT_SEARCH_CASE_SENSITIVE,
        search_highlight_style: Optional[Iterable[str]] = DEFAULT_SEARCH_HIGHLIGHT_STYLE,
        search_key: Optional[str] = DEFAULT_SEARCH_KEY,
        shortcut_brackets_highlight_style: Optional[Iterable[str]] = DEFAULT_SHORTCUT_BRACKETS_HIGHLIGHT_STYLE,
        shortcut_key_highlight_style: Optional[Iterable[str]] = DEFAULT_SHORTCUT_KEY_HIGHLIGHT_STYLE,
        show_multi_select_hint: bool = DEFAULT_SHOW_MULTI_SELECT_HINT,
        show_multi_select_hint_text: Optional[str] = None,
        show_search_hint: bool = DEFAULT_SHOW_SEARCH_HINT,
        show_search_hint_text: Optional[str] = None,
        show_shortcut_hints: bool = DEFAULT_SHOW_SHORTCUT_HINTS,
        show_shortcut_hints_in_status_bar: bool = DEFAULT_SHOW_SHORTCUT_HINTS_IN_STATUS_BAR,
        status_bar: Optional[Union[str, Iterable[str], Callable[[str], str]]] = None,
        status_bar_below_preview: bool = DEFAULT_STATUS_BAR_BELOW_PREVIEW,
        status_bar_style: Optional[Iterable[str]] = DEFAULT_STATUS_BAR_STYLE,
        title: Optional[Union[str, Iterable[str]]] = None
    ):
        def extract_shortcuts_menu_entries_and_preview_arguments(
            entries: Iterable[str],
        ) -> Tuple[List[str], List[str], List[str]]:
            separator_pattern = re.compile(r"([^\\])\|")
            escaped_separator_pattern = re.compile(r"\\\|")
            menu_entry_pattern = re.compile(r"^(?:\[(\S)\]\s*)?([^\x1F]+)(?:\x1F([^\x1F]*))?")
            shortcut_keys = []
            menu_entries = []
            preview_arguments = []
            for entry in entries:
                unit_separated_entry = escaped_separator_pattern.sub("|", separator_pattern.sub("\\1\x1F", entry))
                match_obj = menu_entry_pattern.match(unit_separated_entry)
                assert match_obj is not None
                shortcut_key = match_obj.group(1)
                display_text = match_obj.group(2)
                preview_argument = match_obj.group(3)
                shortcut_keys.append(shortcut_key)
                menu_entries.append(display_text)
                preview_arguments.append(preview_argument)
            return menu_entries, shortcut_keys, preview_arguments

        def convert_preselected_entries_to_indices(
            preselected_indices_or_entries: Iterable[Union[str, int]]
        ) -> Set[int]:
            menu_entry_to_indices = {}  # type: Dict[str, Set[int]]
            for menu_index, menu_entry in enumerate(self._menu_entries):
                menu_entry_to_indices.setdefault(menu_entry, set())
                menu_entry_to_indices[menu_entry].add(menu_index)
            preselected_indices = set()
            for item in preselected_indices_or_entries:
                if isinstance(item, int):
                    if 0 <= item < len(self._menu_entries):
                        preselected_indices.add(item)
                    else:
                        raise IndexError(
                            "Error: {} is outside the allowable range of 0..{}.".format(
                                item, len(self._menu_entries) - 1
                            )
                        )
                elif isinstance(item, str):
                    try:
                        preselected_indices.update(menu_entry_to_indices[item])
                    except KeyError as e:
                        raise UnknownMenuEntryError('Pre-selection "{}" is not a valid menu entry.'.format(item)) from e
                else:
                    raise ValueError('"preselected_entries" must either contain integers or strings.')
            return preselected_indices

        def setup_title_or_status_bar_lines(
            title_or_status_bar: Optional[Union[str, Iterable[str]]],
            show_shortcut_hints: bool,
            menu_entries: Iterable[str],
            shortcut_keys: Iterable[str],
            shortcut_hints_in_parentheses: bool,
        ) -> Tuple[str, ...]:
            if title_or_status_bar is None:
                lines = []  # type: List[str]
            elif isinstance(title_or_status_bar, str):
                lines = title_or_status_bar.split("\n")
            else:
                lines = list(title_or_status_bar)
            if show_shortcut_hints:
                shortcut_hints_line = self._get_shortcut_hints_line(
                    menu_entries, shortcut_keys, shortcut_hints_in_parentheses
                )
                if shortcut_hints_line is not None:
                    lines.append(shortcut_hints_line)
            return tuple(lines)

        (
            self._menu_entries,
            self._shortcut_keys,
            self._preview_arguments,
        ) = extract_shortcuts_menu_entries_and_preview_arguments(menu_entries)
        self._shortcuts_defined = any(key is not None for key in self._shortcut_keys)
        self._accept_keys = tuple(accept_keys)
        self._clear_menu_on_exit = clear_menu_on_exit
        self._clear_screen = clear_screen
        self._cycle_cursor = cycle_cursor
        self._multi_select_empty_ok = multi_select_empty_ok
        self._exit_on_shortcut = exit_on_shortcut
        self._menu_cursor = menu_cursor if menu_cursor is not None else ""
        self._menu_cursor_style = tuple(menu_cursor_style) if menu_cursor_style is not None else ()
        self._menu_highlight_style = tuple(menu_highlight_style) if menu_highlight_style is not None else ()
        self._multi_select = multi_select
        self._multi_select_cursor = multi_select_cursor
        self._multi_select_cursor_brackets_style = (
            tuple(multi_select_cursor_brackets_style) if multi_select_cursor_brackets_style is not None else ()
        )
        self._multi_select_cursor_style = (
            tuple(multi_select_cursor_style) if multi_select_cursor_style is not None else ()
        )
        self._multi_select_keys = tuple(multi_select_keys) if multi_select_keys is not None else ()
        self._multi_select_select_on_accept = multi_select_select_on_accept
        if preselected_entries and not self._multi_select:
            raise InvalidParameterCombinationError(
                "Multi-select mode must be enabled when preselected entries are given."
            )
        self._preselected_indices = (
            convert_preselected_entries_to_indices(preselected_entries) if preselected_entries is not None else None
        )
        self._preview_border = preview_border
        self._preview_command = preview_command
        self._preview_size = preview_size
        self._preview_title = preview_title
        self._search_case_sensitive = search_case_sensitive
        self._search_highlight_style = tuple(search_highlight_style) if search_highlight_style is not None else ()
        self._search_key = search_key
        self._shortcut_brackets_highlight_style = (
            tuple(shortcut_brackets_highlight_style) if shortcut_brackets_highlight_style is not None else ()
        )
        self._shortcut_key_highlight_style = (
            tuple(shortcut_key_highlight_style) if shortcut_key_highlight_style is not None else ()
        )
        self._show_search_hint = show_search_hint
        self._show_search_hint_text = show_search_hint_text
        self._show_shortcut_hints = show_shortcut_hints
        self._show_shortcut_hints_in_status_bar = show_shortcut_hints_in_status_bar
        self._status_bar_func = None  # type: Optional[Callable[[str], str]]
        self._status_bar_lines = None  # type: Optional[Tuple[str, ...]]
        if callable(status_bar):
            self._status_bar_func = status_bar
        else:
            self._status_bar_lines = setup_title_or_status_bar_lines(
                status_bar,
                show_shortcut_hints and show_shortcut_hints_in_status_bar,
                self._menu_entries,
                self._shortcut_keys,
                False,
            )
        self._status_bar_below_preview = status_bar_below_preview
        self._status_bar_style = tuple(status_bar_style) if status_bar_style is not None else ()
        self._title_lines = setup_title_or_status_bar_lines(
            title,
            show_shortcut_hints and not show_shortcut_hints_in_status_bar,
            self._menu_entries,
            self._shortcut_keys,
            True,
        )
        self._show_multi_select_hint = show_multi_select_hint
        self._show_multi_select_hint_text = show_multi_select_hint_text
        self._chosen_accept_key = None  # type: Optional[str]
        self._chosen_menu_index = None  # type: Optional[int]
        self._chosen_menu_indices = None  # type: Optional[Tuple[int, ...]]
        self._paint_before_next_read = False
        self._previous_displayed_menu_height = None  # type: Optional[int]
        self._reading_next_key = False
        self._search = self.Search(
            self._menu_entries,
            case_senitive=self._search_case_sensitive,
            show_search_hint=self._show_search_hint,
        )
        self._selection = self.Selection(len(self._menu_entries), self._preselected_indices)
        self._viewport = self.Viewport(
            len(self._menu_entries),
            len(self._title_lines),
            len(self._status_bar_lines) if self._status_bar_lines is not None else 0,
            0,
            0,
        )
        self._view = self.View(self._menu_entries, self._search, self._selection, self._viewport, self._cycle_cursor)
        if cursor_index and 0 < cursor_index < len(self._menu_entries):
            self._view.active_menu_index = cursor_index
        self._search.change_callback = self._view.update_view
        self._old_term = None  # type: Optional[List[Union[int, List[bytes]]]]
        self._new_term = None  # type: Optional[List[Union[int, List[bytes]]]]
        self._tty_in = None  # type: Optional[TextIO]
        self._tty_out = None  # type: Optional[TextIO]
        self._user_locale = get_locale()
        self._check_for_valid_styles()
        # backspace can be queried from the terminal database but is unreliable, query the terminal directly instead
        self._init_backspace_control_character()
        self._add_missing_control_characters_for_keys(self._accept_keys)
        self._init_terminal_codes()

    @staticmethod
    def _get_shortcut_hints_line(
        menu_entries: Iterable[str],
        shortcut_keys: Iterable[str],
        shortcut_hints_in_parentheses: bool,
    ) -> Optional[str]:
        shortcut_hints_line = ", ".join(
            "[{}]: {}".format(shortcut_key, menu_entry)
            for shortcut_key, menu_entry in zip(shortcut_keys, menu_entries)
            if shortcut_key is not None
        )
        if shortcut_hints_line != "":
            if shortcut_hints_in_parentheses:
                return "(" + shortcut_hints_line + ")"
            else:
                return shortcut_hints_line
        return None

    @staticmethod
    def _get_keycode_for_key(key: str) -> str:
        if len(key) == 1:
            # One letter keys represent themselves
            return key
        alt_modified_regex = re.compile(r"[Aa]lt-(\S)")
        ctrl_modified_regex = re.compile(r"[Cc]trl-(\S)")
        match_obj = alt_modified_regex.match(key)
        if match_obj:
            return "\033" + match_obj.group(1)
        match_obj = ctrl_modified_regex.match(key)
        if match_obj:
            # Ctrl + key is interpreted by terminals as the ascii code of that key minus 64
            ctrl_code_ascii = ord(match_obj.group(1).upper()) - 64
            if ctrl_code_ascii < 0:
                # Interpret negative ascii codes as unsigned 7-Bit integers
                ctrl_code_ascii = ctrl_code_ascii & 0x80 - 1
            return chr(ctrl_code_ascii)
        raise ValueError('Cannot interpret the given key "{}".'.format(key))

    @classmethod
    def _init_backspace_control_character(self) -> None:
        try:
            with open("/dev/tty", "r") as tty:
                stty_output = subprocess.check_output(["stty", "-a"], universal_newlines=True, stdin=tty)
            name_to_keycode_regex = re.compile(r"^\s*(\S+)\s*=\s*\^(\S+)\s*$")
            for field in stty_output.split(";"):
                match_obj = name_to_keycode_regex.match(field)
                if not match_obj:
                    continue
                name, ctrl_code = match_obj.group(1), match_obj.group(2)
                if name != "erase":
                    continue
                self._name_to_control_character["backspace"] = self._get_keycode_for_key("ctrl-" + ctrl_code)
                return
        except subprocess.CalledProcessError:
            pass
        # Backspace control character could not be queried, assume `<Ctrl-?>` (is most often used)
        self._name_to_control_character["backspace"] = "\177"

    @classmethod
    def _add_missing_control_characters_for_keys(cls, keys: Iterable[str]) -> None:
        for key in keys:
            if key not in cls._name_to_control_character and key not in string.ascii_letters:
                cls._name_to_control_character[key] = cls._get_keycode_for_key(key)

    @classmethod
    def _init_terminal_codes(cls) -> None:
        if cls._codename_to_terminal_code is not None:
            return
        supported_colors = int(cls._query_terminfo_database("colors"))
        cls._codename_to_terminal_code = {
            codename: cls._query_terminfo_database(codename)
            if not (codename.startswith("bg_") or codename.startswith("fg_")) or supported_colors >= 8
            else ""
            for codename in cls._codenames
        }
        cls._codename_to_terminal_code.update(cls._name_to_control_character)
        cls._terminal_code_to_codename = {
            terminal_code: codename for codename, terminal_code in cls._codename_to_terminal_code.items()
        }

    @classmethod
    def _query_terminfo_database(cls, codename: str) -> str:
        if codename in cls._codename_to_capname:
            capname = cls._codename_to_capname[codename]
        else:
            capname = codename
        try:
            return subprocess.check_output(["tput"] + capname.split(), universal_newlines=True)
        except subprocess.CalledProcessError as e:
            # The return code 1 indicates a missing terminal capability
            if e.returncode == 1:
                return ""
            raise e

    @classmethod
    def _num_lines(self) -> int:
        return int(self._query_terminfo_database("lines"))

    @classmethod
    def _num_cols(self) -> int:
        return int(self._query_terminfo_database("cols"))

    def _check_for_valid_styles(self) -> None:
        invalid_styles = []
        for style_tuple in (
            self._menu_cursor_style,
            self._menu_highlight_style,
            self._search_highlight_style,
            self._shortcut_key_highlight_style,
            self._shortcut_brackets_highlight_style,
            self._status_bar_style,
            self._multi_select_cursor_brackets_style,
            self._multi_select_cursor_style,
        ):
            for style in style_tuple:
                if style not in self._codename_to_capname:
                    invalid_styles.append(style)
        if invalid_styles:
            if len(invalid_styles) == 1:
                raise InvalidStyleError('The style "{}" does not exist.'.format(invalid_styles[0]))
            else:
                raise InvalidStyleError('The styles ("{}") do not exist.'.format('", "'.join(invalid_styles)))

    def _init_term(self) -> None:
        # pylint: disable=unsubscriptable-object
        assert self._codename_to_terminal_code is not None
        self._tty_in = open("/dev/tty", "r", encoding=self._user_locale)
        self._tty_out = open("/dev/tty", "w", encoding=self._user_locale, errors="replace")
        self._old_term = termios.tcgetattr(self._tty_in.fileno())
        self._new_term = termios.tcgetattr(self._tty_in.fileno())
        # set the terminal to: unbuffered, no echo and no <CR> to <NL> translation (so <enter> sends <CR> instead of
        # <NL, this is necessary to distinguish between <enter> and <Ctrl-j> since <Ctrl-j> generates <NL>)
        self._new_term[3] = cast(int, self._new_term[3]) & ~termios.ICANON & ~termios.ECHO & ~termios.ICRNL
        self._new_term[0] = cast(int, self._new_term[0]) & ~termios.ICRNL
        termios.tcsetattr(
            self._tty_in.fileno(), termios.TCSAFLUSH, cast(List[Union[int, List[Union[bytes, int]]]], self._new_term)
        )
        # Enter terminal application mode to get expected escape codes for arrow keys
        self._tty_out.write(self._codename_to_terminal_code["enter_application_mode"])
        self._tty_out.write(self._codename_to_terminal_code["cursor_invisible"])
        if self._clear_screen:
            self._tty_out.write(self._codename_to_terminal_code["clear"])

    def _reset_term(self) -> None:
        # pylint: disable=unsubscriptable-object
        assert self._codename_to_terminal_code is not None
        assert self._tty_in is not None
        assert self._tty_out is not None
        assert self._old_term is not None
        termios.tcsetattr(
            self._tty_out.fileno(), termios.TCSAFLUSH, cast(List[Union[int, List[Union[bytes, int]]]], self._old_term)
        )
        self._tty_out.write(self._codename_to_terminal_code["cursor_visible"])
        self._tty_out.write(self._codename_to_terminal_code["exit_application_mode"])
        if self._clear_screen:
            self._tty_out.write(self._codename_to_terminal_code["clear"])
        self._tty_in.close()
        self._tty_out.close()

    def _paint_menu(self) -> None:
        def get_status_bar_lines() -> Tuple[str, ...]:
            def get_multi_select_hint() -> str:
                def get_string_from_keys(keys: Sequence[str]) -> str:
                    string_to_key = {
                        " ": "space",
                    }
                    keys_string = ", ".join(
                        "<" + string_to_key.get(accept_key, accept_key) + ">" for accept_key in keys
                    )
                    return keys_string

                accept_keys_string = get_string_from_keys(self._accept_keys)
                multi_select_keys_string = get_string_from_keys(self._multi_select_keys)
                if self._show_multi_select_hint_text is not None:
                    return self._show_multi_select_hint_text.format(
                        multi_select_keys=multi_select_keys_string, accept_keys=accept_keys_string
                    )
                else:
                    return "Press {} for multi-selection and {} to {}accept".format(
                        multi_select_keys_string,
                        accept_keys_string,
                        "select and " if self._multi_select_select_on_accept else "",
                    )

            if self._status_bar_func is not None and self._view.active_menu_index is not None:
                status_bar_lines = tuple(
                    self._status_bar_func(self._menu_entries[self._view.active_menu_index]).strip().split("\n")
                )
                if self._show_shortcut_hints and self._show_shortcut_hints_in_status_bar:
                    shortcut_hints_line = self._get_shortcut_hints_line(self._menu_entries, self._shortcut_keys, False)
                    if shortcut_hints_line is not None:
                        status_bar_lines += (shortcut_hints_line,)
            elif self._status_bar_lines is not None:
                status_bar_lines = self._status_bar_lines
            else:
                status_bar_lines = tuple()
            if self._multi_select and self._show_multi_select_hint:
                status_bar_lines += (get_multi_select_hint(),)
            return status_bar_lines

        def apply_style(
            style_iterable: Optional[Iterable[str]] = None, reset: bool = True, file: Optional[TextIO] = None
        ) -> None:
            # pylint: disable=unsubscriptable-object
            assert self._codename_to_terminal_code is not None
            assert self._tty_out is not None
            if file is None:
                file = self._tty_out
            if reset or style_iterable is None:
                file.write(self._codename_to_terminal_code["reset_attributes"])
            if style_iterable is not None:
                for style in style_iterable:
                    file.write(self._codename_to_terminal_code[style])

        def print_menu_entries() -> int:
            # pylint: disable=unsubscriptable-object
            assert self._codename_to_terminal_code is not None
            assert self._tty_out is not None
            all_cursors_width = wcswidth(self._menu_cursor) + (
                wcswidth(self._multi_select_cursor) if self._multi_select else 0
            )
            current_menu_block_displayed_height = 0  # sum all written lines
            num_cols = self._num_cols()
            if self._title_lines:
                self._tty_out.write(
                    len(self._title_lines) * self._codename_to_terminal_code["cursor_up"]
                    + "\r"
                    + "\n".join(
                        (title_line[:num_cols] + (num_cols - wcswidth(title_line)) * " ")
                        for title_line in self._title_lines
                    )
                    + "\n"
                )
            shortcut_string_len = 4 if self._shortcuts_defined else 0
            displayed_index = -1
            for displayed_index, menu_index, menu_entry in self._view:
                current_shortcut_key = self._shortcut_keys[menu_index]
                self._tty_out.write(all_cursors_width * self._codename_to_terminal_code["cursor_right"])
                if self._shortcuts_defined:
                    if current_shortcut_key is not None:
                        apply_style(self._shortcut_brackets_highlight_style)
                        self._tty_out.write("[")
                        apply_style(self._shortcut_key_highlight_style)
                        self._tty_out.write(current_shortcut_key)
                        apply_style(self._shortcut_brackets_highlight_style)
                        self._tty_out.write("]")
                        apply_style()
                    else:
                        self._tty_out.write(3 * " ")
                    self._tty_out.write(" ")
                if menu_index == self._view.active_menu_index:
                    apply_style(self._menu_highlight_style)
                if self._search and self._search.search_text != "":
                    match_obj = self._search.matches[displayed_index][1]
                    self._tty_out.write(
                        menu_entry[: min(match_obj.start(), num_cols - all_cursors_width - shortcut_string_len)]
                    )
                    apply_style(self._search_highlight_style)
                    self._tty_out.write(
                        menu_entry[
                            match_obj.start() : min(match_obj.end(), num_cols - all_cursors_width - shortcut_string_len)
                        ]
                    )
                    apply_style()
                    if menu_index == self._view.active_menu_index:
                        apply_style(self._menu_highlight_style)
                    self._tty_out.write(
                        menu_entry[match_obj.end() : num_cols - all_cursors_width - shortcut_string_len]
                    )
                else:
                    self._tty_out.write(menu_entry[: num_cols - all_cursors_width - shortcut_string_len])
                if menu_index == self._view.active_menu_index:
                    apply_style()
                self._tty_out.write((num_cols - wcswidth(menu_entry) - all_cursors_width - shortcut_string_len) * " ")
                if displayed_index < self._viewport.upper_index:
                    self._tty_out.write("\n")
            empty_menu_lines = self._viewport.upper_index - displayed_index
            self._tty_out.write(
                max(0, empty_menu_lines - 1) * (num_cols * " " + "\n") + min(1, empty_menu_lines) * (num_cols * " ")
            )
            self._tty_out.write("\r" + (self._viewport.size - 1) * self._codename_to_terminal_code["cursor_up"])
            current_menu_block_displayed_height += self._viewport.size - 1  # sum all written lines
            return current_menu_block_displayed_height

        def print_search_line(current_menu_height: int) -> int:
            # pylint: disable=unsubscriptable-object
            assert self._codename_to_terminal_code is not None
            assert self._tty_out is not None
            current_menu_block_displayed_height = 0
            num_cols = self._num_cols()
            if self._search or self._show_search_hint:
                self._tty_out.write((current_menu_height + 1) * self._codename_to_terminal_code["cursor_down"])
            if self._search:
                assert self._search.search_text is not None
                self._tty_out.write(
                    (
                        (self._search_key if self._search_key is not None else DEFAULT_SEARCH_KEY)
                        + self._search.search_text
                    )[:num_cols]
                )
                self._tty_out.write((num_cols - len(self._search) - 1) * " ")
            elif self._show_search_hint:
                if self._show_search_hint_text is not None:
                    search_hint = self._show_search_hint_text.format(key=self._search_key)[:num_cols]
                elif self._search_key is not None:
                    search_hint = '(Press "{key}" to search)'.format(key=self._search_key)[:num_cols]
                else:
                    search_hint = "(Press any letter key to search)"[:num_cols]
                self._tty_out.write(search_hint)
                self._tty_out.write((num_cols - wcswidth(search_hint)) * " ")
            if self._search or self._show_search_hint:
                self._tty_out.write("\r" + (current_menu_height + 1) * self._codename_to_terminal_code["cursor_up"])
                current_menu_block_displayed_height = 1
            return current_menu_block_displayed_height

        def print_status_bar(current_menu_height: int, status_bar_lines: Tuple[str, ...]) -> int:
            # pylint: disable=unsubscriptable-object
            assert self._codename_to_terminal_code is not None
            assert self._tty_out is not None
            current_menu_block_displayed_height = 0  # sum all written lines
            num_cols = self._num_cols()
            if status_bar_lines:
                self._tty_out.write((current_menu_height + 1) * self._codename_to_terminal_code["cursor_down"])
                apply_style(self._status_bar_style)
                self._tty_out.write(
                    "\r"
                    + "\n".join(
                        (status_bar_line[:num_cols] + (num_cols - wcswidth(status_bar_line)) * " ")
                        for status_bar_line in status_bar_lines
                    )
                    + "\r"
                )
                apply_style()
                self._tty_out.write(
                    (current_menu_height + len(status_bar_lines)) * self._codename_to_terminal_code["cursor_up"]
                )
                current_menu_block_displayed_height += len(status_bar_lines)
            return current_menu_block_displayed_height

        def print_preview(current_menu_height: int, preview_max_num_lines: int) -> int:
            # pylint: disable=unsubscriptable-object
            assert self._codename_to_terminal_code is not None
            assert self._tty_out is not None
            if self._preview_command is None or preview_max_num_lines < 3:
                return 0

            def get_preview_string() -> Optional[str]:
                assert self._preview_command is not None
                if self._view.active_menu_index is None:
                    return None
                preview_argument = (
                    self._preview_arguments[self._view.active_menu_index]
                    if self._preview_arguments[self._view.active_menu_index] is not None
                    else self._menu_entries[self._view.active_menu_index]
                )
                if preview_argument == "":
                    return None
                if isinstance(self._preview_command, str):
                    try:
                        preview_process = subprocess.Popen(
                            [cmd_part.format(preview_argument) for cmd_part in shlex.split(self._preview_command)],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                        )
                        assert preview_process.stdout is not None
                        preview_string = (
                            io.TextIOWrapper(preview_process.stdout, encoding=self._user_locale, errors="replace")
                            .read()
                            .strip()
                        )
                    except subprocess.CalledProcessError as e:
                        raise PreviewCommandFailedError(
                            e.stderr.decode(encoding=self._user_locale, errors="replace").strip()
                        ) from e
                else:
                    preview_string = self._preview_command(preview_argument)
                return preview_string

            @static_variables(
                # Regex taken from https://stackoverflow.com/a/14693789/5958465
                ansi_escape_regex=re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])"),
                # Modified version of https://stackoverflow.com/a/2188410/5958465
                ansi_sgr_regex=re.compile(r"\x1B\[[;\d]*m"),
            )
            def strip_ansi_codes_except_styling(string: str) -> str:
                stripped_string = strip_ansi_codes_except_styling.ansi_escape_regex.sub(  # type: ignore
                    lambda match_obj: match_obj.group(0)
                    if strip_ansi_codes_except_styling.ansi_sgr_regex.match(match_obj.group(0))  # type: ignore
                    else "",
                    string,
                )
                return cast(str, stripped_string)

            @static_variables(
                regular_text_regex=re.compile(r"([^\x1B]+)(.*)"),
                ansi_escape_regex=re.compile(r"(\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~]))(.*)"),
            )
            def limit_string_with_escape_codes(string: str, max_len: int) -> Tuple[str, int]:
                if max_len <= 0:
                    return "", 0
                string_parts = []
                string_len = 0
                while string:
                    regular_text_match = limit_string_with_escape_codes.regular_text_regex.match(string)  # type: ignore
                    if regular_text_match is not None:
                        regular_text = regular_text_match.group(1)
                        regular_text_len = wcswidth(regular_text)
                        if string_len + regular_text_len > max_len:
                            string_parts.append(regular_text[: max_len - string_len])
                            string_len = max_len
                            break
                        string_parts.append(regular_text)
                        string_len += regular_text_len
                        string = regular_text_match.group(2)
                    else:
                        ansi_escape_match = limit_string_with_escape_codes.ansi_escape_regex.match(  # type: ignore
                            string
                        )
                        if ansi_escape_match is not None:
                            # Adopt the ansi escape code but do not count its length
                            ansi_escape_code_text = ansi_escape_match.group(1)
                            string_parts.append(ansi_escape_code_text)
                            string = ansi_escape_match.group(2)
                        else:
                            # It looks like an escape code (starts with escape), but it is something else
                            # -> skip the escape character and continue the loop
                            string_parts.append("\x1B")
                            string = string[1:]
                return "".join(string_parts), string_len

            num_cols = self._num_cols()
            try:
                preview_string = get_preview_string()
                if preview_string is not None:
                    preview_string = strip_ansi_codes_except_styling(preview_string)
            except PreviewCommandFailedError as e:
                preview_string = "The preview command failed with error message:\n\n" + str(e)
            self._tty_out.write(current_menu_height * self._codename_to_terminal_code["cursor_down"])
            if preview_string is not None:
                self._tty_out.write(self._codename_to_terminal_code["cursor_down"] + "\r")
                if self._preview_border:
                    self._tty_out.write(
                        (
                            BoxDrawingCharacters.upper_left
                            + (2 * BoxDrawingCharacters.horizontal + " " + self._preview_title)[: num_cols - 3]
                            + " "
                            + (num_cols - len(self._preview_title) - 6) * BoxDrawingCharacters.horizontal
                            + BoxDrawingCharacters.upper_right
                        )[:num_cols]
                        + "\n"
                    )
                # `finditer` can be used as a generator version of `str.join`
                for i, line in enumerate(
                    match.group(0) for match in re.finditer(r"^.*$", preview_string, re.MULTILINE)
                ):
                    if i >= preview_max_num_lines - (2 if self._preview_border else 0):
                        preview_num_lines = preview_max_num_lines
                        break
                    limited_line, limited_line_len = limit_string_with_escape_codes(
                        line, num_cols - (3 if self._preview_border else 0)
                    )
                    self._tty_out.write(
                        (
                            ((BoxDrawingCharacters.vertical + " ") if self._preview_border else "")
                            + limited_line
                            + self._codename_to_terminal_code["reset_attributes"]
                            + max(num_cols - limited_line_len - (3 if self._preview_border else 0), 0) * " "
                            + (BoxDrawingCharacters.vertical if self._preview_border else "")
                        )
                    )
                else:
                    preview_num_lines = i + (3 if self._preview_border else 1)
                if self._preview_border:
                    self._tty_out.write(
                        "\n"
                        + (
                            BoxDrawingCharacters.lower_left
                            + (num_cols - 2) * BoxDrawingCharacters.horizontal
                            + BoxDrawingCharacters.lower_right
                        )[:num_cols]
                    )
                self._tty_out.write("\r")
            else:
                preview_num_lines = 0
            self._tty_out.write(
                (current_menu_height + preview_num_lines) * self._codename_to_terminal_code["cursor_up"]
            )
            return preview_num_lines

        def delete_old_menu_lines(displayed_menu_height: int) -> None:
            # pylint: disable=unsubscriptable-object
            assert self._codename_to_terminal_code is not None
            assert self._tty_out is not None
            if (
                self._previous_displayed_menu_height is not None
                and self._previous_displayed_menu_height > displayed_menu_height
            ):
                self._tty_out.write((displayed_menu_height + 1) * self._codename_to_terminal_code["cursor_down"])
                self._tty_out.write(
                    (self._previous_displayed_menu_height - displayed_menu_height)
                    * self._codename_to_terminal_code["delete_line"]
                )
                self._tty_out.write((displayed_menu_height + 1) * self._codename_to_terminal_code["cursor_up"])

        def position_cursor() -> None:
            # pylint: disable=unsubscriptable-object
            assert self._codename_to_terminal_code is not None
            assert self._tty_out is not None
            if self._view.active_displayed_index is None:
                return

            cursor_width = wcswidth(self._menu_cursor)
            for displayed_index in range(self._viewport.lower_index, self._viewport.upper_index + 1):
                if displayed_index == self._view.active_displayed_index:
                    apply_style(self._menu_cursor_style)
                    self._tty_out.write(self._menu_cursor)
                    apply_style()
                else:
                    self._tty_out.write(cursor_width * " ")
                self._tty_out.write("\r")
                if displayed_index < self._viewport.upper_index:
                    self._tty_out.write(self._codename_to_terminal_code["cursor_down"])
            self._tty_out.write((self._viewport.size - 1) * self._codename_to_terminal_code["cursor_up"])

        def print_multi_select_column() -> None:
            # pylint: disable=unsubscriptable-object
            assert self._codename_to_terminal_code is not None
            assert self._tty_out is not None
            if not self._multi_select:
                return

            def prepare_multi_select_cursors() -> Tuple[str, str]:
                bracket_characters = "([{<)]}>"
                bracket_style_escape_codes_io = io.StringIO()
                multi_select_cursor_style_escape_codes_io = io.StringIO()
                reset_codes_io = io.StringIO()
                apply_style(self._multi_select_cursor_brackets_style, file=bracket_style_escape_codes_io)
                apply_style(self._multi_select_cursor_style, file=multi_select_cursor_style_escape_codes_io)
                apply_style(file=reset_codes_io)
                bracket_style_escape_codes = bracket_style_escape_codes_io.getvalue()
                multi_select_cursor_style_escape_codes = multi_select_cursor_style_escape_codes_io.getvalue()
                reset_codes = reset_codes_io.getvalue()

                cursor_with_brackets_only = re.sub(
                    r"[^{}]".format(re.escape(bracket_characters)), " ", self._multi_select_cursor
                )
                cursor_with_brackets_only_styled = re.sub(
                    r"[{}]+".format(re.escape(bracket_characters)),
                    lambda match_obj: bracket_style_escape_codes + match_obj.group(0) + reset_codes,
                    cursor_with_brackets_only,
                )
                cursor_styled = re.sub(
                    r"[{brackets}]+|[^{brackets}\s]+".format(brackets=re.escape(bracket_characters)),
                    lambda match_obj: (
                        bracket_style_escape_codes
                        if match_obj.group(0)[0] in bracket_characters
                        else multi_select_cursor_style_escape_codes
                    )
                    + match_obj.group(0)
                    + reset_codes,
                    self._multi_select_cursor,
                )
                return cursor_styled, cursor_with_brackets_only_styled

            if not self._view:
                return
            checked_multi_select_cursor, unchecked_multi_select_cursor = prepare_multi_select_cursors()
            cursor_width = wcswidth(self._menu_cursor)
            displayed_selected_indices = self._view.displayed_selected_indices
            displayed_index = 0
            for displayed_index, _, _ in self._view:
                self._tty_out.write("\r" + cursor_width * self._codename_to_terminal_code["cursor_right"])
                if displayed_index in displayed_selected_indices:
                    self._tty_out.write(checked_multi_select_cursor)
                else:
                    self._tty_out.write(unchecked_multi_select_cursor)
                if displayed_index < self._viewport.upper_index:
                    self._tty_out.write(self._codename_to_terminal_code["cursor_down"])
            self._tty_out.write("\r")
            self._tty_out.write(
                (displayed_index + (1 if displayed_index < self._viewport.upper_index else 0))
                * self._codename_to_terminal_code["cursor_up"]
            )

        # pylint: disable=unsubscriptable-object
        assert self._codename_to_terminal_code is not None
        assert self._tty_out is not None
        displayed_menu_height = 0  # sum all written lines
        status_bar_lines = get_status_bar_lines()
        self._viewport.status_bar_lines_count = len(status_bar_lines)
        if self._preview_command is not None:
            self._viewport.preview_lines_count = int(self._preview_size * self._num_lines())
            preview_max_num_lines = self._viewport.preview_lines_count
        self._viewport.keep_visible(self._view.active_displayed_index)
        displayed_menu_height += print_menu_entries()
        displayed_menu_height += print_search_line(displayed_menu_height)
        if not self._status_bar_below_preview:
            displayed_menu_height += print_status_bar(displayed_menu_height, status_bar_lines)
        if self._preview_command is not None:
            displayed_menu_height += print_preview(displayed_menu_height, preview_max_num_lines)
        if self._status_bar_below_preview:
            displayed_menu_height += print_status_bar(displayed_menu_height, status_bar_lines)
        delete_old_menu_lines(displayed_menu_height)
        position_cursor()
        if self._multi_select:
            print_multi_select_column()
        self._previous_displayed_menu_height = displayed_menu_height
        self._tty_out.flush()

    def _clear_menu(self) -> None:
        # pylint: disable=unsubscriptable-object
        assert self._codename_to_terminal_code is not None
        assert self._previous_displayed_menu_height is not None
        assert self._tty_out is not None
        if self._clear_menu_on_exit:
            if self._title_lines:
                self._tty_out.write(len(self._title_lines) * self._codename_to_terminal_code["cursor_up"])
                self._tty_out.write(len(self._title_lines) * self._codename_to_terminal_code["delete_line"])
            self._tty_out.write(
                (self._previous_displayed_menu_height + 1) * self._codename_to_terminal_code["delete_line"]
            )
        else:
            self._tty_out.write(
                (self._previous_displayed_menu_height + 1) * self._codename_to_terminal_code["cursor_down"]
            )
        self._tty_out.flush()

    def _read_next_key(self, ignore_case: bool = True) -> str:
        # pylint: disable=unsubscriptable-object,unsupported-membership-test
        assert self._terminal_code_to_codename is not None
        assert self._tty_in is not None
        # Needed for asynchronous handling of terminal resize events
        self._reading_next_key = True
        if self._paint_before_next_read:
            self._paint_menu()
            self._paint_before_next_read = False
        # blocks until any amount of bytes is available
        code = os.read(self._tty_in.fileno(), 80).decode("ascii", errors="ignore")
        self._reading_next_key = False
        if code in self._terminal_code_to_codename:
            return self._terminal_code_to_codename[code]
        elif ignore_case:
            return code.lower()
        else:
            return code

    def show(self) -> Optional[Union[int, Tuple[int, ...]]]:
        def init_signal_handling() -> None:
            # `SIGWINCH` is send on terminal resizes
            def handle_sigwinch(signum: signal.Signals, frame: FrameType) -> None:
                # pylint: disable=unused-argument
                if self._reading_next_key:
                    self._paint_menu()
                else:
                    self._paint_before_next_read = True

            signal.signal(signal.SIGWINCH, handle_sigwinch)

        def reset_signal_handling() -> None:
            signal.signal(signal.SIGWINCH, signal.SIG_DFL)

        def remove_letter_keys(menu_action_to_keys: Dict[str, Set[Optional[str]]]) -> None:
            letter_keys = frozenset(string.ascii_lowercase) | frozenset(" ")
            for keys in menu_action_to_keys.values():
                keys -= letter_keys

        # pylint: disable=unsubscriptable-object
        assert self._codename_to_terminal_code is not None
        self._init_term()
        if self._preselected_indices is None:
            self._selection.clear()
        self._chosen_accept_key = None
        self._chosen_menu_indices = None
        self._chosen_menu_index = None
        assert self._tty_out is not None
        if self._title_lines:
            # `print_menu` expects the cursor on the first menu item -> reserve one line for the title
            self._tty_out.write(len(self._title_lines) * self._codename_to_terminal_code["cursor_down"])
        menu_was_interrupted = False
        try:
            init_signal_handling()
            menu_action_to_keys = {
                "menu_up": set(("up", "ctrl-k", "k")),
                "menu_down": set(("down", "ctrl-j", "j")),
                "accept": set(self._accept_keys),
                "multi_select": set(self._multi_select_keys),
                "quit": set(("escape", "q")),
                "search_start": set((self._search_key,)),
                "backspace": set(("backspace",)),
            }  # type: Dict[str, Set[Optional[str]]]
            while True:
                self._paint_menu()
                current_menu_action_to_keys = copy.deepcopy(menu_action_to_keys)
                next_key = self._read_next_key(ignore_case=False)
                if self._search or self._search_key is None:
                    remove_letter_keys(current_menu_action_to_keys)
                else:
                    next_key = next_key.lower()
                if self._search_key is not None and not self._search and next_key in self._shortcut_keys:
                    shortcut_menu_index = self._shortcut_keys.index(next_key)
                    if self._exit_on_shortcut:
                        self._selection.add(shortcut_menu_index)
                        break
                    else:
                        if self._multi_select:
                            self._selection.toggle(shortcut_menu_index)
                        else:
                            self._view.active_menu_index = shortcut_menu_index
                elif next_key in current_menu_action_to_keys["menu_up"]:
                    self._view.decrement_active_index()
                elif next_key in current_menu_action_to_keys["menu_down"]:
                    self._view.increment_active_index()
                elif self._multi_select and next_key in current_menu_action_to_keys["multi_select"]:
                    if self._view.active_menu_index is not None:
                        self._selection.toggle(self._view.active_menu_index)
                elif next_key in current_menu_action_to_keys["accept"]:
                    if self._view.active_menu_index is not None:
                        if self._multi_select_select_on_accept or (
                            not self._selection and self._multi_select_empty_ok is False
                        ):
                            self._selection.add(self._view.active_menu_index)
                    self._chosen_accept_key = next_key
                    break
                elif next_key in current_menu_action_to_keys["quit"]:
                    if not self._search:
                        menu_was_interrupted = True
                        break
                    else:
                        self._search.search_text = None
                elif not self._search:
                    if next_key in current_menu_action_to_keys["search_start"] or (
                        self._search_key is None and next_key == DEFAULT_SEARCH_KEY
                    ):
                        self._search.search_text = ""
                    elif self._search_key is None:
                        self._search.search_text = next_key
                else:
                    assert self._search.search_text is not None
                    if next_key in ("backspace",):
                        if self._search.search_text != "":
                            self._search.search_text = self._search.search_text[:-1]
                        else:
                            self._search.search_text = None
                    elif wcswidth(next_key) >= 0 and not (
                        next_key in current_menu_action_to_keys["search_start"] and self._search.search_text == ""
                    ):
                        # Only append `next_key` if it is a printable character and the first character is not the
                        # `search_start` key
                        self._search.search_text += next_key
        except KeyboardInterrupt:
            menu_was_interrupted = True
        finally:
            reset_signal_handling()
            self._clear_menu()
            self._reset_term()
        if not menu_was_interrupted:
            chosen_menu_indices = self._selection.selected_menu_indices
            if chosen_menu_indices:
                if self._multi_select:
                    self._chosen_menu_indices = chosen_menu_indices
                else:
                    self._chosen_menu_index = chosen_menu_indices[0]
        return self._chosen_menu_indices if self._multi_select else self._chosen_menu_index

    @property
    def chosen_accept_key(self) -> Optional[str]:
        return self._chosen_accept_key

    @property
    def chosen_menu_entry(self) -> Optional[str]:
        return self._menu_entries[self._chosen_menu_index] if self._chosen_menu_index is not None else None

    @property
    def chosen_menu_entries(self) -> Optional[Tuple[str, ...]]:
        return (
            tuple(self._menu_entries[menu_index] for menu_index in self._chosen_menu_indices)
            if self._chosen_menu_indices is not None
            else None
        )

    @property
    def chosen_menu_index(self) -> Optional[int]:
        return self._chosen_menu_index

    @property
    def chosen_menu_indices(self) -> Optional[Tuple[int, ...]]:
        return self._chosen_menu_indices


class AttributeDict(dict):  # type: ignore
    def __getattr__(self, attr: str) -> Any:
        return self[attr]

    def __setattr__(self, attr: str, value: Any) -> None:
        self[attr] = value


def get_argumentparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="""
%(prog)s creates simple interactive menus in the terminal and returns the selected entry as exit code.
""",
    )
    parser.add_argument(
        "-s", "--case-sensitive", action="store_true", dest="case_sensitive", help="searches are case sensitive"
    )
    parser.add_argument(
        "-X",
        "--no-clear-menu-on-exit",
        action="store_false",
        dest="clear_menu_on_exit",
        help="do not clear the menu on exit",
    )
    parser.add_argument(
        "-l",
        "--clear-screen",
        action="store_true",
        dest="clear_screen",
        help="clear the screen before the menu is shown",
    )
    parser.add_argument(
        "--cursor",
        action="store",
        dest="cursor",
        default=DEFAULT_MENU_CURSOR,
        help='menu cursor (default: "%(default)s")',
    )
    parser.add_argument(
        "-i",
        "--cursor-index",
        action="store",
        dest="cursor_index",
        type=int,
        default=0,
        help="initially selected item index",
    )
    parser.add_argument(
        "--cursor-style",
        action="store",
        dest="cursor_style",
        default=",".join(DEFAULT_MENU_CURSOR_STYLE),
        help='style for the menu cursor as comma separated list (default: "%(default)s")',
    )
    parser.add_argument("-C", "--no-cycle", action="store_false", dest="cycle", help="do not cycle the menu selection")
    parser.add_argument(
        "-E",
        "--no-exit-on-shortcut",
        action="store_false",
        dest="exit_on_shortcut",
        help="do not exit on shortcut keys",
    )
    parser.add_argument(
        "--highlight-style",
        action="store",
        dest="highlight_style",
        default=",".join(DEFAULT_MENU_HIGHLIGHT_STYLE),
        help='style for the selected menu entry as comma separated list (default: "%(default)s")',
    )
    parser.add_argument(
        "-m",
        "--multi-select",
        action="store_true",
        dest="multi_select",
        help="Allow the selection of multiple entries (implies `--stdout`)",
    )
    parser.add_argument(
        "--multi-select-cursor",
        action="store",
        dest="multi_select_cursor",
        default=DEFAULT_MULTI_SELECT_CURSOR,
        help='multi-select menu cursor (default: "%(default)s")',
    )
    parser.add_argument(
        "--multi-select-cursor-brackets-style",
        action="store",
        dest="multi_select_cursor_brackets_style",
        default=",".join(DEFAULT_MULTI_SELECT_CURSOR_BRACKETS_STYLE),
        help='style for brackets of the multi-select menu cursor as comma separated list (default: "%(default)s")',
    )
    parser.add_argument(
        "--multi-select-cursor-style",
        action="store",
        dest="multi_select_cursor_style",
        default=",".join(DEFAULT_MULTI_SELECT_CURSOR_STYLE),
        help='style for the multi-select menu cursor as comma separated list (default: "%(default)s")',
    )
    parser.add_argument(
        "--multi-select-keys",
        action="store",
        dest="multi_select_keys",
        default=",".join(DEFAULT_MULTI_SELECT_KEYS),
        help=('key for toggling a selected item in a multi-selection (default: "%(default)s", '),
    )
    parser.add_argument(
        "--multi-select-no-select-on-accept",
        action="store_false",
        dest="multi_select_select_on_accept",
        help=(
            "do not select the currently highlighted menu item when the accept key is pressed "
            "(it is still selected if no other item was selected before)"
        ),
    )
    parser.add_argument(
        "--multi-select-empty-ok",
        action="store_true",
        dest="multi_select_empty_ok",
        help=("when used together with --multi-select-no-select-on-accept allows returning no selection at all"),
    )
    parser.add_argument(
        "-p",
        "--preview",
        action="store",
        dest="preview_command",
        help=(
            "Command to generate a preview for the selected menu entry. "
            '"{}" can be used as placeholder for the menu text. '
            'If the menu entry has a data component (separated by "|"), this is used instead.'
        ),
    )
    parser.add_argument(
        "--no-preview-border",
        action="store_false",
        dest="preview_border",
        help="do not draw a border around the preview window",
    )
    parser.add_argument(
        "--preview-size",
        action="store",
        dest="preview_size",
        type=float,
        default=DEFAULT_PREVIEW_SIZE,
        help='maximum height of the preview window in fractions of the terminal height (default: "%(default)s")',
    )
    parser.add_argument(
        "--preview-title",
        action="store",
        dest="preview_title",
        default=DEFAULT_PREVIEW_TITLE,
        help='title of the preview window (default: "%(default)s")',
    )
    parser.add_argument(
        "--search-highlight-style",
        action="store",
        dest="search_highlight_style",
        default=",".join(DEFAULT_SEARCH_HIGHLIGHT_STYLE),
        help='style of matched search patterns (default: "%(default)s")',
    )
    parser.add_argument(
        "--search-key",
        action="store",
        dest="search_key",
        default=DEFAULT_SEARCH_KEY,
        help=(
            'key to start a search (default: "%(default)s", '
            '"none" is treated a special value which activates the search on any letter key)'
        ),
    )
    parser.add_argument(
        "--shortcut-brackets-highlight-style",
        action="store",
        dest="shortcut_brackets_highlight_style",
        default=",".join(DEFAULT_SHORTCUT_BRACKETS_HIGHLIGHT_STYLE),
        help='style of brackets enclosing shortcut keys (default: "%(default)s")',
    )
    parser.add_argument(
        "--shortcut-key-highlight-style",
        action="store",
        dest="shortcut_key_highlight_style",
        default=",".join(DEFAULT_SHORTCUT_KEY_HIGHLIGHT_STYLE),
        help='style of shortcut keys (default: "%(default)s")',
    )
    parser.add_argument(
        "--show-multi-select-hint",
        action="store_true",
        dest="show_multi_select_hint",
        help="show a multi-select hint in the status bar",
    )
    parser.add_argument(
        "--show-multi-select-hint-text",
        action="store",
        dest="show_multi_select_hint_text",
        help=(
            "Custom text which will be shown as multi-select hint. Use the placeholders {multi_select_keys} and "
            "{accept_keys} if appropriately."
        ),
    )
    parser.add_argument(
        "--show-search-hint",
        action="store_true",
        dest="show_search_hint",
        help="show a search hint in the search line",
    )
    parser.add_argument(
        "--show-search-hint-text",
        action="store",
        dest="show_search_hint_text",
        help=(
            "Custom text which will be shown as search hint. Use the placeholders {key} for the search key "
            "if appropriately."
        ),
    )
    parser.add_argument(
        "--show-shortcut-hints",
        action="store_true",
        dest="show_shortcut_hints",
        help="show shortcut hints in the status bar",
    )
    parser.add_argument(
        "--show-shortcut-hints-in-title",
        action="store_false",
        dest="show_shortcut_hints_in_status_bar",
        default=True,
        help="show shortcut hints in the menu title",
    )
    parser.add_argument(
        "-b",
        "--status-bar",
        action="store",
        dest="status_bar",
        help="status bar text",
    )
    parser.add_argument(
        "-d",
        "--status-bar-below-preview",
        action="store_true",
        dest="status_bar_below_preview",
        help="show the status bar below the preview window if any",
    )
    parser.add_argument(
        "--status-bar-style",
        action="store",
        dest="status_bar_style",
        default=",".join(DEFAULT_STATUS_BAR_STYLE),
        help='style of the status bar lines (default: "%(default)s")',
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        dest="stdout",
        help=(
            "Print the selected menu index or indices to stdout (in addition to the exit status). "
            'Multiple indices are separated by ";".'
        ),
    )
    parser.add_argument("-t", "--title", action="store", dest="title", help="menu title")
    parser.add_argument(
        "-V", "--version", action="store_true", dest="print_version", help="print the version number and exit"
    )
    parser.add_argument("entries", action="store", nargs="*", help="the menu entries to show")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-r",
        "--preselected_entries",
        action="store",
        dest="preselected_entries",
        help="Comma separated list of strings matching menu items to start pre-selected in a multi-select menu.",
    )
    group.add_argument(
        "-R",
        "--preselected_indices",
        action="store",
        dest="preselected_indices",
        help="Comma separated list of numeric indexes of menu items to start pre-selected in a multi-select menu.",
    )
    return parser


def parse_arguments() -> AttributeDict:
    parser = get_argumentparser()
    args = AttributeDict({key: value for key, value in vars(parser.parse_args()).items()})
    if not args.print_version and not args.entries:
        raise NoMenuEntriesError("No menu entries given!")
    if args.cursor_style != "":
        args.cursor_style = tuple(args.cursor_style.split(","))
    else:
        args.cursor_style = None
    if args.highlight_style != "":
        args.highlight_style = tuple(args.highlight_style.split(","))
    else:
        args.highlight_style = None
    if args.search_highlight_style != "":
        args.search_highlight_style = tuple(args.search_highlight_style.split(","))
    else:
        args.search_highlight_style = None
    if args.shortcut_key_highlight_style != "":
        args.shortcut_key_highlight_style = tuple(args.shortcut_key_highlight_style.split(","))
    else:
        args.shortcut_key_highlight_style = None
    if args.shortcut_brackets_highlight_style != "":
        args.shortcut_brackets_highlight_style = tuple(args.shortcut_brackets_highlight_style.split(","))
    else:
        args.shortcut_brackets_highlight_style = None
    if args.status_bar_style != "":
        args.status_bar_style = tuple(args.status_bar_style.split(","))
    else:
        args.status_bar_style = None
    if args.multi_select_cursor_brackets_style != "":
        args.multi_select_cursor_brackets_style = tuple(args.multi_select_cursor_brackets_style.split(","))
    else:
        args.multi_select_cursor_brackets_style = None
    if args.multi_select_cursor_style != "":
        args.multi_select_cursor_style = tuple(args.multi_select_cursor_style.split(","))
    else:
        args.multi_select_cursor_style = None
    if args.multi_select_keys != "":
        args.multi_select_keys = tuple(args.multi_select_keys.split(","))
    else:
        args.multi_select_keys = None
    if args.search_key.lower() == "none":
        args.search_key = None
    if args.show_shortcut_hints_in_status_bar:
        args.show_shortcut_hints = True
    if args.multi_select:
        args.stdout = True
    if args.preselected_entries is not None:
        args.preselected = list(args.preselected_entries.split(","))
    elif args.preselected_indices is not None:
        args.preselected = list(map(int, args.preselected_indices.split(",")))
    else:
        args.preselected = None
    return args


def main() -> None:
    try:
        args = parse_arguments()
    except SystemExit:
        sys.exit(0)  # Error code 0 is the error case in this program
    except NoMenuEntriesError as e:
        print(str(e), file=sys.stderr)
        sys.exit(0)
    if args.print_version:
        print("{}, version {}".format(os.path.basename(sys.argv[0]), __version__))
        sys.exit(0)
    try:
        terminal_menu = TerminalMenu(
            menu_entries=args.entries,
            clear_menu_on_exit=args.clear_menu_on_exit,
            clear_screen=args.clear_screen,
            cursor_index=args.cursor_index,
            cycle_cursor=args.cycle,
            exit_on_shortcut=args.exit_on_shortcut,
            menu_cursor=args.cursor,
            menu_cursor_style=args.cursor_style,
            menu_highlight_style=args.highlight_style,
            multi_select=args.multi_select,
            multi_select_cursor=args.multi_select_cursor,
            multi_select_cursor_brackets_style=args.multi_select_cursor_brackets_style,
            multi_select_cursor_style=args.multi_select_cursor_style,
            multi_select_empty_ok=args.multi_select_empty_ok,
            multi_select_keys=args.multi_select_keys,
            multi_select_select_on_accept=args.multi_select_select_on_accept,
            preselected_entries=args.preselected,
            preview_border=args.preview_border,
            preview_command=args.preview_command,
            preview_size=args.preview_size,
            preview_title=args.preview_title,
            search_case_sensitive=args.case_sensitive,
            search_highlight_style=args.search_highlight_style,
            search_key=args.search_key,
            shortcut_brackets_highlight_style=args.shortcut_brackets_highlight_style,
            shortcut_key_highlight_style=args.shortcut_key_highlight_style,
            show_multi_select_hint=args.show_multi_select_hint,
            show_multi_select_hint_text=args.show_multi_select_hint_text,
            show_search_hint=args.show_search_hint,
            show_search_hint_text=args.show_search_hint_text,
            show_shortcut_hints=args.show_shortcut_hints,
            show_shortcut_hints_in_status_bar=args.show_shortcut_hints_in_status_bar,
            status_bar=args.status_bar,
            status_bar_below_preview=args.status_bar_below_preview,
            status_bar_style=args.status_bar_style,
            title=args.title,
        )
    except (InvalidParameterCombinationError, InvalidStyleError, UnknownMenuEntryError) as e:
        print(str(e), file=sys.stderr)
        sys.exit(0)
    chosen_entries = terminal_menu.show()
    if chosen_entries is None:
        sys.exit(0)
    else:
        if isinstance(chosen_entries, Iterable):
            if args.stdout:
                print(",".join(str(entry + 1) for entry in chosen_entries))
            sys.exit(chosen_entries[0] + 1)
        else:
            chosen_entry = chosen_entries
            if args.stdout:
                print(chosen_entry + 1)
            sys.exit(chosen_entry + 1)


if __name__ == "__main__":
    main()
