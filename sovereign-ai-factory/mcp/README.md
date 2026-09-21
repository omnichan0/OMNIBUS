# MCP layer

This directory is reserved for MCP servers/bridges.

The architecture deliberately keeps MCP behind Open WebUI:

    Open WebUI -> MCP/tool layer -> capability/adapters -> providers

The current factory script does not claim to implement a full MCP server.
Add concrete MCP servers here as capabilities are integrated.
