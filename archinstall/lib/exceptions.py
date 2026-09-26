class RequirementError(Exception):
	pass


class DiskError(Exception):
	pass


class UnknownFilesystemFormatError(Exception):
	pass


class SysCallError(Exception):
	def __init__(self, message: str, exit_code: int | None = None, worker_log: bytes = b'') -> None:
		super().__init__(message)
		self.message = message
		self.exit_code = exit_code
		self.worker_log = worker_log


class HardwareIncompatibilityError(Exception):
	pass


class ServiceExceptionError(Exception):
	pass


class PackageError(Exception):
	pass


class DeprecatedError(Exception):
	pass


class DownloadTimeoutError(Exception):
	"""
	Download timeout exception raised by DownloadTimer.
	"""
