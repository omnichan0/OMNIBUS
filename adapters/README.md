# Adapters

Adapters are backend capabilities, not additional user interfaces.

Rules:
- Open WebUI remains the primary UI.
- Integrations are exposed through MCP, HTTP APIs, or backend adapters.
- Do not hard-code one Hugging Face Space as "the video provider".
- Discover implementations at runtime where practical.
- Check repository licenses and third-party terms before incorporating code.
- Public/authorized data only for cameras, feeds, and similar sources.
