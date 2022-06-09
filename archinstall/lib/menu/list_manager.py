#!/usr/bin/python
"""
# Purpose
ListManager is a widget based on `menu` which allows the handling of repetitive operations in a list.
Imagine you have a list and want to add/copy/edit/delete their elements. With this widget you will be shown the list
```
Vamos alla

Use ESC to skip


> uno : 1
dos : 2
tres : 3
cuatro : 4
==>
Confirm and exit
Cancel
(Press "/" to search)
```
Once you select one of the elements of the list, you will be promted with the action to be done to the selected element
```

uno : 1
dos : 2
> tres : 3
cuatro : 4
==>
Confirm and exit
Cancel
(Press "/" to search)

Select an action for < {'tres': 3} >


Add
Copy
Edit
Delete
> Cancel
```
You execute the action for this element (which might or not involve user interaction) and return to the list main page
till you call one of the options `confirm and exit` which returns the modified list or `cancel` which returns the original list unchanged.
If the list is empty one action can be defined as default (usually Add). We call it **null_action**
YOu can also define a **default_action** which will appear below the separator, not tied to any element of the list. Barring explicit definition, default_action will be the null_action
```
==>
Add
Confirm and exit
Cancel
(Press "/" to search)
```
The default implementation can handle simple lists and a key:value dictionary. The default actions are the shown above.
A sample of basic usage is included at the end of the source.

More sophisticaded uses can be achieved by
* changing the action list and the null_action during initialization
```
	opciones = ListManager('Vamos alla',opciones,[str(_('Add')),str(_('Delete'))],_('Add')).run()
```
* And using following methods to overwrite/define user actions and other details:
* * `reformat`. To change the appearance of the list elements
* * `action_list`. To modify the content of the action list once an element is defined. F.i. to avoid Delete to appear for certain elements, or to add/modify action based in the value of the element.
* * `exec_action` which contains the actual code to be executed when an action is selected

The contents in the base class of this methods serve for a very basic usage, and are to be taken as samples. Thus the best use of this class would be to subclass in your code

```
	class ObjectList(archinstall.ListManager):
		def __init__(prompt,list):
			self.ObjectAction = [... list of actions ...]
			self.ObjectNullAction = one ObjectAction
			super().__init__(prompt,list,ObjectActions,ObjectNullAction)
		def reformat(self):
			... beautfy the output of the list
		def action_list(self):
			... if you need some changes to the action list based on self.target
		def exec_action(self):
			if self.action == self.ObjectAction[0]:
				performFirstAction(self.target, ...)

	...
	resultList = ObjectList(prompt,originallist).run()
```

"""
import copy
from os import system
from typing import Union, Any, TYPE_CHECKING, Dict, Optional, Tuple, List

from .text_input import TextInput
from .menu import Menu

if TYPE_CHECKING:
	_: Any


class ListManager:
	def __init__(
		self,
		prompt :str,
		base_list :Union[list,dict] ,
		base_actions :list = None,
		null_action :str = None,
		default_action :Union[str,list] = None,
		header :Union[str,list] = None):
		"""
		param :prompt  Text which will appear at the header
		type param: string | DeferredTranslation

		param :base:_list list/dict of option to be shown / mainpulated
		type param: list | dict

		param base_actions an alternate list of actions to the items of the object
		type param: list

		param: null_action action which will be taken (if any) when base_list is empty
		type param: string

		param: default_action action which will be presented at the bottom of the list. Shouldn't need a target. If not present, null_action is set there.
		Both Null and Default actions can be defined outside the base_actions list, as long as they are launched in exec_action
		type param: string or list

		param: header one or more header lines for the list
		type param: string or list
		"""

		explainer = str(_('\n Choose an object from the list, and select one of the available actions for it to execute'))
		self._prompt = prompt + explainer if prompt else explainer

		self._null_action = str(null_action) if null_action else None

		if not default_action:
			self._default_action = [self._null_action]
		elif isinstance(default_action,(list,tuple)):
			self._default_action = default_action
		else:
			self._default_action = [str(default_action)]

		self._header = header if header else ''
		self._cancel_action = str(_('Cancel'))
		self._confirm_action = str(_('Confirm and exit'))
		self._separator = ''
		self._bottom_list = [self._confirm_action, self._cancel_action]
		self._bottom_item = [self._cancel_action]
		self._base_actions = base_actions if base_actions else [str(_('Add')), str(_('Copy')), str(_('Edit')), str(_('Delete'))]
		self._original_data = copy.deepcopy(base_list)
		self._data = copy.deepcopy(base_list) # as refs, changes are immediate

		# default values for the null case
		self.target: Optional[Any] = None
		self.action = self._null_action

	def run(self):
		while True:
			# this will return a dictionary with the key as the menu entry to be displayed
			# and the value is the original value from the self._data container
			data_formatted = self.reformat(self._data)
			options, header = self._prepare_selection(data_formatted)

			menu_header = self._header

			if header:
				menu_header += header

			system('clear')

			choice = Menu(
				self._prompt,
				options,
				sort=False,
				clear_screen=False,
				clear_menu_on_exit=False,
				header=header,
				skip_empty_entries=True,
				skip=False,
				show_search_hint=False
			).run()

			if not choice.value or choice.value in self._bottom_list:
				self.action = choice
				break

			if choice.value and choice.value in self._default_action:
				self.action = choice.value
				self.target = None
				self._data = self.exec_action(self._data)
				continue

			if isinstance(self._data, dict):
				data_key = data_formatted[choice.value]
				key = self._data[data_key]
				self.target = {data_key: key}
			elif isinstance(self._data, list):
				self.target = [d for d in self._data if d == data_formatted[choice.value]][0]
			else:
				self.target = self._data[data_formatted[choice.value]]

			# Possible enhancement. If run_actions returns false a message line indicating the failure
			self.run_actions(choice.value)

		if choice.value == self._cancel_action:
			return self._original_data  # return the original list
		else:
			return self._data

	def _prepare_selection(self, data_formatted: Dict[str, Any]) -> Tuple[List[str], str]:
		# header rows are mapped to None so make sure
		# to exclude those from the selectable data
		options: List[str] = [key for key, val in data_formatted.items() if val is not None]
		header = ''

		if len(options) > 0:
			table_header = [key for key, val in data_formatted.items() if val is None]
			header = '\n'.join(table_header)

		if len(options) > 0:
			options.append(self._separator)

		if self._default_action:
			# done only for mypy -> todo fix the self._default_action declaration
			options += [action for action in self._default_action if action]

		options += self._bottom_list
		return options, header

	def run_actions(self,prompt_data=''):
		options = self.action_list() + self._bottom_item
		display_value = self.selected_action_display(self.target) if self.target else prompt_data

		prompt = _("Select an action for '{}'").format(display_value)

		choice = Menu(
			prompt,
			options,
			sort=False,
			clear_screen=False,
			clear_menu_on_exit=False,
			preset_values=self._bottom_item,
			show_search_hint=False
		).run()

		self.action = choice.value

		if self.action and self.action != self._cancel_action:
			self._data = self.exec_action(self._data)

	def selected_action_display(self, selection: Any) -> str:
		# this will return the value to be displayed in the
		# "Select an action for '{}'" string
		raise NotImplementedError('Please implement me in the child class')

	def reformat(self, data: List[Any]) -> Dict[str, Any]:
		# this should return a dictionary of display string to actual data entry
		# mapping; if the value for a given display string is None it will be used
		# in the header value (useful when displaying tables)
		raise NotImplementedError('Please implement me in the child class')

	def action_list(self):
		"""
		can define alternate action list or customize the list  for each item.
		Executed after any item is selected, contained in self.target
		"""
		active_entry = self.target if self.target else None

		if active_entry is None:
			return [self._base_actions[0]]
		else:
			return self._base_actions[1:]

	def exec_action(self, data: Any):
		"""
		what's executed one an item (self.target) and one action (self.action) is selected.
		Should be overwritten by the user
		The result is expected to update self._data in this routine, else it is ignored
		The basic code is useful for simple lists and dictionaries (key:value pairs, both strings)
		"""
		# TODO guarantee unicity
		if isinstance(self._data,list):
			if self.action == str(_('Add')):
				self.target = TextInput(_('Add: '),None).run()
				self._data.append(self.target)
			if self.action == str(_('Copy')):
				while True:
					target = TextInput(_('Copy to: '),self.target).run()
					if target != self.target:
						self._data.append(self.target)
						break
			elif self.action == str(_('Edit')):
				tgt = self.target
				idx = self._data.index(self.target)
				result = TextInput(_('Edit: '),tgt).run()
				self._data[idx] = result
			elif self.action == str(_('Delete')):
				del self._data[self._data.index(self.target)]
		elif isinstance(self._data,dict):
			# allows overwrites
			if self.target:
				origkey,origval = list(self.target.items())[0]
			else:
				origkey = None
				origval = None
			if self.action == str(_('Add')):
				key = TextInput(_('Key: '),None).run()
				value = TextInput(_('Value: '),None).run()
				self._data[key] = value
			if self.action == str(_('Copy')):
				while True:
					key = TextInput(_('Copy to new key:'),origkey).run()
					if key != origkey:
						self._data[key] = origval
						break
			elif self.action == str(_('Edit')):
				value = TextInput(_('Edit {}: ').format(origkey), origval).run()
				self._data[origkey] = value
			elif self.action == str(_('Delete')):
				del self._data[origkey]

		return self._data
