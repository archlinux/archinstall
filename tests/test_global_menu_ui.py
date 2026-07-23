import asyncio
import inspect
from unittest.mock import MagicMock


class MockSpecialMenuKey:
	SAVE = 'save'
	INSTALL = 'install'
	ABORT = 'abort'


class MockMenuItem:
	def __init__(self, key=None, read_only=False, mandatory=False, value=None):
		self.key = key
		self.read_only = read_only
		self.mandatory = mandatory
		self.value = value

	def has_value(self):
		return self.value is not None


def isolated_get_status_prefix(item: MockMenuItem) -> str:
	special_keys = (MockSpecialMenuKey.SAVE, MockSpecialMenuKey.INSTALL, MockSpecialMenuKey.ABORT)

	if item.read_only or item.key in special_keys:
		return ''

	if item.key == 'auth_config':
		auth_config = item.value
		has_root = getattr(auth_config, 'root_enc_password', None) is not None
		has_super = getattr(auth_config, 'has_superuser', lambda: False)() if auth_config else False

		if auth_config is not None and (has_root or has_super):
			return '[bold green][✓][/bold green] '
		return '[bold red][!][/bold red] '

	if item.has_value():
		return '[bold green][✓][/bold green] '
	elif item.mandatory:
		return '[bold red][!][/bold red] '
	else:
		return '[bold yellow][•][/bold yellow] '


def isolated_wrap_action(item_dictionary, update_callback, key, action):

	async def wrapper(*args, **kwargs):
		if inspect.iscoroutinefunction(action):
			result = await action(*args, **kwargs)
		else:
			result = action(*args, **kwargs)
			if inspect.isawaitable(result):
				result = await result

		if key in item_dictionary:
			item_dictionary[key].value = result

		update_callback()
		return result

	return wrapper


class TestPrefixLogic:
	def test_special_keys_have_no_prefix(self):
		item = MockMenuItem(key=MockSpecialMenuKey.SAVE)
		assert isolated_get_status_prefix(item) == ''

	def test_read_only_has_no_prefix(self):
		item = MockMenuItem(read_only=True)
		assert isolated_get_status_prefix(item) == ''

	def test_configured_item_has_checkmark(self):
		item = MockMenuItem(key='hostname', value='archlinux')
		prefix = isolated_get_status_prefix(item)
		assert '[✓]' in prefix
		assert 'green' in prefix

	def test_missing_mandatory_item_has_warning(self):
		item = MockMenuItem(key='disk_config', mandatory=True, value=None)
		prefix = isolated_get_status_prefix(item)
		assert '[!]' in prefix
		assert 'red' in prefix

	def test_missing_optional_item_has_dot(self):
		item = MockMenuItem(key='network_config', mandatory=False, value=None)
		prefix = isolated_get_status_prefix(item)
		assert '[•]' in prefix
		assert 'yellow' in prefix


class TestAuthConfigLogic:
	def test_auth_missing_entirely(self):
		item = MockMenuItem(key='auth_config', value=None)
		assert '[!]' in isolated_get_status_prefix(item)

	def test_auth_invalid_state(self):
		mock_auth = MagicMock()
		mock_auth.root_enc_password = None
		mock_auth.has_superuser.return_value = False

		item = MockMenuItem(key='auth_config', value=mock_auth)
		assert '[!]' in isolated_get_status_prefix(item)

	def test_auth_valid_root(self):
		mock_auth = MagicMock()
		mock_auth.root_enc_password = 'hashed'
		mock_auth.has_superuser.return_value = False

		item = MockMenuItem(key='auth_config', value=mock_auth)
		assert '[✓]' in isolated_get_status_prefix(item)

	def test_auth_valid_superuser(self):
		mock_auth = MagicMock()
		mock_auth.root_enc_password = None
		mock_auth.has_superuser.return_value = True

		item = MockMenuItem(key='auth_config', value=mock_auth)
		assert '[✓]' in isolated_get_status_prefix(item)


class TestActionWrapperLogic:
	def test_async_action_updates_value(self):
		mock_item = MockMenuItem(key='disk')
		item_dict = {'disk': mock_item}
		update_spy = MagicMock()

		async def dummy_async_action():
			return 'new_disk_layout'

		wrapped = isolated_wrap_action(item_dict, update_spy, 'disk', dummy_async_action)

		result = asyncio.run(wrapped())

		assert result == 'new_disk_layout'
		assert mock_item.value == 'new_disk_layout'
		update_spy.assert_called_once()

	def test_sync_action_updates_value(self):
		mock_item = MockMenuItem(key='hostname')
		item_dict = {'hostname': mock_item}
		update_spy = MagicMock()

		def dummy_sync_action():
			return 'my-pc'

		wrapped = isolated_wrap_action(item_dict, update_spy, 'hostname', dummy_sync_action)

		result = asyncio.run(wrapped())

		assert result == 'my-pc'
		assert mock_item.value == 'my-pc'
		update_spy.assert_called_once()
