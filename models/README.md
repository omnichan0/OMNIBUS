# Models

Model files are runtime assets, not GitHub assets.

The installer reports available RAM and disk before downloading. On Replit it uses a CPU profile and asks for a small model repository/file or a public GGUF URL. On Colab/Linux, press Enter to use the defaults or set `SOVEREIGN_CHOOSE_MODELS=1` to choose explicitly.

Supported input forms:

- Hugging Face repository: `owner/repository`
- Repository and file: `owner/repository/file.gguf`
- Public resolve URL: `https://huggingface.co/owner/repository/resolve/main/file.gguf`

Public GGUF files are downloaded from Hugging Face resolve URLs with resumable retries. `HF_TOKEN` is not required for ordinary public GGUF downloads. It is reserved for optional authenticated agent capabilities such as Hugging Face Spaces, HF MCP tools, gated repositories, and private resources.

Existing valid local and Drive copies are reused. Model files are intentionally not committed to Git.
