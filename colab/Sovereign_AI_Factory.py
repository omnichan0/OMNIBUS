# Colab helper cell: clone then launch.
# Replace REPO_URL with your GitHub repository URL.
import os, subprocess

REPO_URL = os.environ.get("SOVEREIGN_REPO_URL", "YOUR_GITHUB_REPO_URL")
subprocess.run(["git", "clone", REPO_URL, "/content/sovereign-ai-repo"], check=True)
subprocess.run(
    ["bash", "-lc", "cd /content/sovereign-ai-repo && chmod +x install.sh && ./install.sh"],
    check=True,
)
