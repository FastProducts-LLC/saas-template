"""File upload and storage errors."""

from app.core.exceptions import AppError, ConflictError, NotFoundError


class FileNotFound(NotFoundError):
    code = "file_not_found"
    internal_code = "ERR_FILE_001"


class UploadTooLarge(AppError):
    status_code = 413
    code = "upload_too_large"
    internal_code = "ERR_FILE_002"


class UnsupportedFileType(AppError):
    status_code = 415
    code = "unsupported_file_type"
    internal_code = "ERR_FILE_003"


class UploadNotCompleted(ConflictError):
    code = "upload_not_completed"
    internal_code = "ERR_FILE_004"


class StorageUnavailable(AppError):
    status_code = 503
    code = "storage_unavailable"
    internal_code = "ERR_FILE_005"


class UploadQuotaExceeded(AppError):
    status_code = 429
    code = "upload_quota_exceeded"
    internal_code = "ERR_FILE_006"
