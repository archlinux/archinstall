from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
	from .general import SysCommandWorker

class RequirementError(BaseException):
	pass


class DiskError(BaseException):
	pass


class UnknownFilesystemFormat(BaseException):
	pass


class ProfileError(BaseException):
	pass


class SysCallError(BaseException):
	def __init__(self, message :str, exit_code :Optional[int] = None, worker :Optional['SysCommandWorker'] = None) -> None:
		super(SysCallError, self).__init__(message)
		self.message = message
		self.exit_code = exit_code
		self.worker = worker


class PermissionError(BaseException):
	pass


class ProfileNotFound(BaseException):
	pass


class HardwareIncompatibilityError(BaseException):
	pass


class UserError(BaseException):
	pass


class ServiceException(BaseException):
	pass


class PackageError(BaseException):
	pass


class TranslationError(BaseException):
	pass


class Deprecated(BaseException):
	pass