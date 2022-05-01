import pytest

def test_SysCommand():
	import archinstall
	import subprocess

	if not archinstall.SysCommand('whoami').decode().strip() == subprocess.check_output('whoami').decode().strip():
		raise AssertionError(f"SysCommand('whoami') did not return expected output: {subprocess.check_output('whoami').decode()}")

	try:
		archinstall.SysCommand('nonexistingbinary-for-testing').decode().strip()
	except archinstall.RequirementError:
		pass # we want to make sure it fails with an exception unique to missing binary

	try:
		archinstall.SysCommand('ls -veryfaultyparameter').decode().strip()
	except archinstall.SysCallError:
		pass # We want it to raise a syscall error when a binary dislikes us