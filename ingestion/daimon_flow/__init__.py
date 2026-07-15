"""Daimon's workflow engine: a typed, executable node graph.

Nodes are Daimon's capabilities (triggers, the agent, tools/resources, logic,
outputs). Two kinds of port keep the canvas clean — solid *flow* edges carry
execution, dotted *resource* edges attach dependencies (model, memory, knowledge,
tools) to the agent. The same Registry/Factory/Strategy patterns as daimon_kb."""

__version__ = "0.1.0"
