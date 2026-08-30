"""Read-only, user-authorized Chrome practice-scan boundary."""

from .adapter import ChromeReadOnlyAdapter
from .cursor import ScanCursor
from .models import ChromePageSnapshot, ChromeScanAuthorization
from .security import ConfirmationRequired, CursorError, ScanBlocked, ScopeViolation

__all__ = [
    "ChromePageSnapshot",
    "ChromeReadOnlyAdapter",
    "ChromeScanAuthorization",
    "ConfirmationRequired",
    "CursorError",
    "ScanBlocked",
    "ScanCursor",
    "ScopeViolation",
]
