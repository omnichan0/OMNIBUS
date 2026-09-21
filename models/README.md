# Models

Model files are runtime assets, not GitHub assets.

The factory reuses existing GGUFs whenever possible. For the default public models, it discovers the selected GGUF in the Hugging Face repository and downloads it from the public `resolve` URL with resumable retries. An `HF_TOKEN` is **not required** for ordinary public GGUF downloads.

`HF_TOKEN` is reserved for optional authenticated Hugging Face capabilities used by the agent, such as gated/private models, Spaces, MCP servers, or other Hugging Face tools.

You can override model repositories/files with the `SOVEREIGN_*_REPO` and `SOVEREIGN_*_FILE` environment variables. Model downloads are stored locally or in the mounted Drive cache and are intentionally not committed to Git.
