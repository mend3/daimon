"""Source adapters. Importing this package registers the built-ins (their modules
call @register at import time). New in-tree adapters: add a module and import it
here. Out-of-tree adapters: ship a package with an `ella_kb.adapters` entry point."""
from . import files, urls, chat, feeds, webhook  # noqa: F401  (import-for-registration)
