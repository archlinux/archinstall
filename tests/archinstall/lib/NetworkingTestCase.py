import unittest
from unittest.mock import patch

import archinstall.lib.general
import archinstall.lib.networking


class NetworkingTest(unittest.TestCase):

    @patch.object(archinstall.lib.networking.os, 'geteuid')
    @patch.object(archinstall.lib.general.SysCommand, '__init__')
    @patch.object(archinstall.lib.general.SysCommand, 'exit_code')
    def test_mirror_reachable(self, mock_exit_code, mock_init, mock_geteuid):
        mock_exit_code.return_value = 0
        mock_init.return_value = None
        mock_geteuid.return_value = 0

        is_mirror_reachable = archinstall.check_mirror_reachable()
        self.assertTrue(self, is_mirror_reachable)

    @patch.object(archinstall.lib.networking.os, 'geteuid')
    @patch.object(archinstall.lib.general.SysCommand, '__init__')
    @patch.object(archinstall.lib.general.SysCommand, 'exit_code')
    def test_mirror_is_not_reachable(self, mock_exit_code, mock_init, mock_geteuid):
        mock_exit_code.return_value = 1
        mock_init.return_value = None
        mock_geteuid.return_value = 0

        is_mirror_reachable = archinstall.check_mirror_reachable()
        self.assertTrue(self, not is_mirror_reachable)
