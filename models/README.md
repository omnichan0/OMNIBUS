# OMNIBUS model selection

The installer checks available RAM and disk before the model step. On Replit or another interactive CPU host it asks whether to use the automatic model choice or to provide either:

- a Hugging Face repository, for example `TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF`;
- a repository plus file, for example `TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf`;
- a full public Hugging Face resolve URL.

The installer resolves a repository/file choice to the public Hugging Face download URL. Public GGUF downloads do not require `HF_TOKEN`; that token is reserved for optional agent capabilities such as Spaces, HF MCP tools, gated repositories, or private resources.

Existing valid local and Google Drive copies are reused. Interrupted downloads resume from their `.part` file and retry. Keep at least the model size plus several GB of free disk for temporary files and runtime use.

Replit is best used with a small quantized GGUF and CPU mode. Large coder models may not fit its RAM or may be too slow. Colab with a GPU is the better target for the default larger models.
