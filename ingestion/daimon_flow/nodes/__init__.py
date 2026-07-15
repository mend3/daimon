"""Node handlers. Importing this package registers the built-in node types (each
module calls @node at import). New node types: add a module and import it here, or
ship one out-of-tree via an `daimon_flow.nodes` entry point."""
from . import triggers, agent, resources, logic, outputs  # noqa: F401
