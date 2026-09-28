
# Dress rehearsal (CA #800): with TGF_REHEARSAL=1 every outbound connection
# is refused the moment any email_parser module is imported. No-op otherwise.
from .rehearsal import guard as _rehearsal_guard  # noqa: E402
_rehearsal_guard()
