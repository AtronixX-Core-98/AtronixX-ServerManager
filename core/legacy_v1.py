"""
Compatibility with data created by the pre-release (private) builds that were used before 1.0.0.

Only needed when upgrading such an installation: it lets this version read the old database file,
old encrypted fields and old backup files. If you never ran a pre-release build you can safely
delete this file; everything else keeps working without it.
"""

FIELD_KDF_INFO = b"atronixx-servermanager/fields/v1"
BACKUP_MAGIC = b"ATXBAK1"
DB_FILENAME = "atronixx.db"
