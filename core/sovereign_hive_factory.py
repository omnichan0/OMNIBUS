#!/usr/bin/env python3
# =====================================================================
#  SOVEREIGN HIVE FACTORY v4  -  Colab-ready, Drive-persistent, self-healing
#
#  ONE public door:  ngrok -> Open WebUI :3000
#  Everything else is bound to 127.0.0.1 and talks internally:
#
#     Open WebUI :3000 --(API key)--> Sovereign gateway :8000 --> llama.cpp :8081
#                                        |  1200-agent hive, RAG, SQLite
#     Open WebUI Computer :8100 (local)   Cline CLI --> gateway (auto-configured)
#
#  Survival design (phone screen off / cell interrupted / tab closed):
#     * every service is a detached daemon (own session), NOT a notebook child
#     * a supervisor daemon restarts anything that dies, with backoff
#     * models, llama.cpp build, venv, chat DBs and the public URL live on
#       Google Drive, so a recycled runtime comes back with one command
#
#  Usage (inside Colab, after mounting Drive):
#     python sovereign_hive_factory.py --bootstrap --run-free
#     python sovereign_hive_factory.py --status | --url | --stop | --sync
# =====================================================================
from __future__ import annotations

import argparse
import contextlib
import hashlib
import http.client
import json
import logging
import os
import platform
import random
import re
import secrets
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import tarfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------


def _env(*names: str, default: str = "") -> str:
    for n in names:
        v = os.environ.get(n, "").strip()
        if v:
            return v
    return default


def _flag(name: str, default: bool) -> bool:
    v = os.environ.get(name, "").strip().lower()
    return default if not v else v in ("1", "true", "yes", "on")


def _detect_colab() -> bool:
    return (
        any(k.startswith("COLAB_") for k in os.environ)
        or Path("/content/sample_data").exists()
        or "google.colab" in sys.modules
    )


IS_COLAB = _detect_colab()

ROOT = Path(
    _env("SOVEREIGN_ROOT")
    or ("/content/sovereign-ai" if IS_COLAB else str(Path.home() / "sovereign-ai"))
).expanduser().resolve()


def _detect_persist() -> Optional[Path]:
    p = _env("SOVEREIGN_PERSIST")
    if p:
        return Path(p).expanduser()
    drive = Path("/content/drive/MyDrive")
    if IS_COLAB and drive.is_dir():
        return drive / "sovereign-ai"
    return None


PERSIST = _detect_persist()

BIN = ROOT / "bin"
SRC = ROOT / "src"
MODELS = ROOT / "models"
DATA = ROOT / "data"
LOGS = ROOT / "logs"
RUN = ROOT / "run"
WORKSPACE = ROOT / "workspace"
VENV = ROOT / ".venv"
PYDIR = ROOT / "pythons"
NPM_PREFIX = ROOT / "npm"
SELF = ROOT / "sovereign_hive_factory.py"

LLAMA_SRC = SRC / "llama.cpp"
LLAMA_SERVER = Path(_env("SOVEREIGN_LLAMA_SERVER") or (LLAMA_SRC / "build" / "bin" / "llama-server"))
LLAMA_BIN_DIR = LLAMA_SERVER.parent

DB_PATH = DATA / "sovereign.db"
WEBUI_DATA = DATA / "open-webui"

API_HOST = _env("SOVEREIGN_API_HOST", default="127.0.0.1")
API_PORT = int(_env("SOVEREIGN_API_PORT", default="8000"))
LLAMA_HOST = "127.0.0.1"
LLAMA_PORT = int(_env("SOVEREIGN_LLAMA_PORT", default="8081"))
WEBUI_HOST = "127.0.0.1"
WEBUI_PORT = int(_env("SOVEREIGN_WEBUI_PORT", default="3000"))
COMPUTER_HOST = "127.0.0.1"
COMPUTER_PORT = int(_env("SOVEREIGN_COMPUTER_PORT", default="8100"))
NGROK_API = "http://127.0.0.1:4040"

ENABLE_COMPUTER = _flag("ENABLE_COMPUTER", True)
EXPOSE_COMPUTER = _flag("EXPOSE_COMPUTER", False)  # second public tunnel: OFF by default (it is a shell!)
NGROK_TOKEN = _env("NGROK_AUTHTOKEN", "NGROK_TOKEN")
NGROK_DOMAIN = _env("NGROK_DOMAIN")
HF_TOKEN = _env("HF_TOKEN")

PY_VERSION = _env("SOVEREIGN_PY", default="3.11")  # Open WebUI supports 3.11/3.12, NOT 3.13
OPENWEBUI_SPEC = _env("SOVEREIGN_OPENWEBUI_SPEC", default="open-webui")

REASONING_REPO = _env("SOVEREIGN_REASONING_REPO", "R1_REPO", default="unsloth/DeepSeek-R1-Distill-Qwen-1.5B-GGUF")
CODER_REPO = _env("SOVEREIGN_CODER_REPO", "CODER_REPO", default="bartowski/WhiteRabbitNeo-2.5-Coder-7B-GGUF")
REASONING_FILE = _env("SOVEREIGN_REASONING_FILE", "R1_FILE")
CODER_FILE = _env("SOVEREIGN_CODER_FILE", "CODER_FILE")
REASONING_QUANT = _env("SOVEREIGN_REASONING_QUANT", default="f16").lower()
CODER_QUANT = _env("SOVEREIGN_CODER_QUANT", default="q4_k_m").lower()

MODEL_IDS = {"reasoning": "sovereign-reasoning", "coder": "sovereign-coder", "auto": "sovereign-auto"}

LLAMA_CTX = int(_env("LLAMA_CTX", default="8192"))
REQUEST_TIMEOUT = float(_env("REQUEST_TIMEOUT", default="900"))
STARTUP_TIMEOUT = float(_env("STARTUP_TIMEOUT", default="600"))

NUM_ELITE, NUM_SUPPORT = 500, 700
TOTAL_AGENTS = NUM_ELITE + NUM_SUPPORT
GOSSIP_INTERVAL = int(_env("GOSSIP_INTERVAL", default="60"))
GOSSIP_PAIRS = int(_env("GOSSIP_PAIRS", default="20"))
HEALTH_INTERVAL = 30

FREE_MODE = False  # set from --run-free
PROCS: Dict[str, subprocess.Popen] = {}
PROC_LOCK = threading.RLock()

log = logging.getLogger("sovereign")


def setup_logging(mode: str) -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    handlers: List[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if mode == "bootstrap":  # daemons already have stdout redirected into their own log file
        handlers.append(logging.FileHandler(LOGS / "bootstrap.log", encoding="utf-8"))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s", handlers=handlers)


def say(msg: str = "") -> None:
    print(msg, flush=True)


def banner(title: str) -> None:
    say(f"\n{'=' * 72}\n {title}\n{'=' * 72}")


def ok(m: str) -> None:
    say(f"[✓] {m}")


def info(m: str) -> None:
    say(f"[•] {m}")


def warn(m: str) -> None:
    say(f"[!] {m}")


def fail(m: str) -> None:
    say(f"[✗] {m}")


def prepare_dirs() -> None:
    for d in (ROOT, BIN, SRC, MODELS, DATA, LOGS, RUN, WORKSPACE, WEBUI_DATA):
        d.mkdir(parents=True, exist_ok=True)


def _secret(fname: str, env_name: str = "") -> str:
    v = _env(env_name) if env_name else ""
    if v:
        return v
    f = DATA / fname
    if f.exists() and f.read_text().strip():
        return f.read_text().strip()
    DATA.mkdir(parents=True, exist_ok=True)
    v = secrets.token_urlsafe(32)
    f.write_text(v)
    with contextlib.suppress(OSError):
        os.chmod(f, 0o600)
    return v


def api_key() -> str:
    return _secret("api_key", "SOVEREIGN_API_KEY")


# ---------------------------------------------------------------------
# GENERAL HELPERS
# ---------------------------------------------------------------------


def port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1.5):
            return True
    except OSError:
        return False


def wait_port_closed(host: str, port: int, timeout: float = 30) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if not port_open(host, port):
            return True
        time.sleep(0.25)
    return False


def http_get(url: str, timeout: float = 5, headers: Optional[Dict[str, str]] = None) -> Tuple[int, bytes]:
    try:
        req = urllib.request.Request(url, headers=headers or {})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        with contextlib.suppress(Exception):
            return e.code, e.read()
        return e.code, b""
    except Exception:
        return 0, b""


def http_ok(url: str, timeout: float = 5, headers: Optional[Dict[str, str]] = None) -> bool:
    s, _ = http_get(url, timeout, headers)
    return 200 <= s < 400


def http_json(method: str, url: str, body: Any = None, headers: Optional[Dict[str, str]] = None,
              timeout: float = 30) -> Tuple[int, Any]:
    h = {"Content-Type": "application/json", **(headers or {})}
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            code = r.status
    except urllib.error.HTTPError as e:
        raw, code = (e.read() or b""), e.code
    except Exception as e:
        return 0, {"error": str(e)}
    try:
        return code, json.loads(raw.decode() or "null")
    except Exception:
        return code, {"raw": raw[:500].decode(errors="replace")}


def api_url(path: str) -> str:
    return f"http://{API_HOST}:{API_PORT}{path}"


def api_headers() -> Dict[str, str]:
    return {"Authorization": f"Bearer {api_key()}"}


def webui_url(path: str = "/") -> str:
    return f"http://{WEBUI_HOST}:{WEBUI_PORT}{path}"


def sh(cmd: Any, *, check: bool = True, capture: bool = False, cwd: Optional[Path] = None,
       env: Optional[Dict[str, str]] = None, timeout: Optional[float] = None, quiet: bool = False,
       stdin_null: bool = True) -> subprocess.CompletedProcess:
    """Run a command. Output streams live (so you can watch builds) unless capture=True."""
    is_str = isinstance(cmd, str)
    shown = cmd if is_str else " ".join(map(str, cmd))
    if not quiet:
        log.info("$ %s", shown)
    full_env = {**os.environ, **env} if env else None
    try:
        r = subprocess.run(
            cmd if is_str else [str(x) for x in cmd], shell=is_str, cwd=str(cwd) if cwd else None,
            env=full_env, timeout=timeout, text=True,
            stdout=subprocess.PIPE if capture else None, stderr=subprocess.STDOUT if capture else None,
            stdin=subprocess.DEVNULL if stdin_null else None,
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"Timed out after {timeout}s: {'<hidden>' if quiet else shown}") from e
    except OSError as e:
        raise RuntimeError(f"Cannot run {'<hidden>' if quiet else shown}: {e}") from e
    if check and r.returncode != 0:
        tail = (r.stdout or "")[-3000:] if capture else ""
        raise RuntimeError(f"Command failed ({r.returncode}): {'<hidden>' if quiet else shown}\n{tail}")
    return r


def download(url: str, dest: Path, token: str = "") -> None:
    """Resumable download via curl (strips auth on cross-host redirects, retries, -C - resume)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    cmd = ["curl", "-fL", "--retry", "8", "--retry-delay", "5", "--retry-all-errors", "-C", "-",
           "--progress-bar", "-o", str(part), url]
    if token:
        cmd[1:1] = ["-H", f"Authorization: Bearer {token}"]
    sh(cmd, quiet=bool(token))
    os.replace(part, dest)


# ---------------------------------------------------------------------
# PROCESS MANAGEMENT  (detached daemons + pidfiles; survives cell death)
# ---------------------------------------------------------------------

_OURS = ("llama-server", "open-webui", "ngrok", "cptr", "sovereign_hive_factory")


def _pidfile(name: str) -> Path:
    return RUN / f"{name}.pid"


def _read_pid(name: str) -> Optional[int]:
    try:
        return int(_pidfile(name).read_text().strip())
    except (OSError, ValueError):
        return None


def _is_ours(pid: int) -> bool:
    if not Path("/proc").exists():
        return True
    try:
        text = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
    except OSError:
        return False
    return any(k in text for k in _OURS)


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    with contextlib.suppress(OSError):  # zombie children count as dead
        if Path(f"/proc/{pid}/stat").read_text().split(") ")[-1].startswith("Z"):
            return False
    return True


def process_running(name: str) -> bool:
    with PROC_LOCK:
        p = PROCS.get(name)
    if p is not None:
        return p.poll() is None
    pid = _read_pid(name)
    return bool(pid and _pid_alive(pid) and _is_ours(pid))


def spawn(name: str, cmd: List[Any], *, cwd: Optional[Path] = None, env: Optional[Dict[str, str]] = None) -> subprocess.Popen:
    stop_process(name)
    RUN.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    e = {**os.environ, **(env or {})}
    log.info("Starting %s: %s", name, " ".join(map(str, cmd))[:300])
    with open(LOGS / f"{name}.log", "ab") as fh:
        p = subprocess.Popen([str(x) for x in cmd], cwd=str(cwd) if cwd else None, env=e, stdout=fh,
                             stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
    with PROC_LOCK:
        PROCS[name] = p
    _pidfile(name).write_text(str(p.pid))
    return p


def stop_process(name: str, timeout: float = 20) -> None:
    with PROC_LOCK:
        proc = PROCS.pop(name, None)
    pid = proc.pid if proc else _read_pid(name)
    if pid is None or pid == os.getpid():
        return
    if proc is None and not (_pid_alive(pid) and _is_ours(pid)):
        _pidfile(name).unlink(missing_ok=True)
        return

    def alive() -> bool:
        return proc.poll() is None if proc is not None else _pid_alive(pid)

    log.info("Stopping %s (pid=%s)", name, pid)
    for sig, wait in ((signal.SIGTERM, timeout), (signal.SIGKILL, 5)):
        try:
            pgid = os.getpgid(pid)
            if pgid == os.getpgrp():
                os.kill(pid, sig)
            else:
                os.killpg(pgid, sig)
        except OSError:
            break
        end = time.monotonic() + wait
        while time.monotonic() < end and alive():
            time.sleep(0.2)
        if not alive():
            break
    _pidfile(name).unlink(missing_ok=True)


def stop_all() -> None:
    names = set(PROCS) | {f.stem for f in RUN.glob("*.pid")}
    order = ["supervisor", "ngrok", "computer", "openwebui", "api", "llama"]
    for n in sorted(names, key=lambda x: order.index(x) if x in order else -1):
        stop_process(n)
    if kill_stray_llama():
        time.sleep(2)
        kill_stray_llama(signal.SIGKILL)


def kill_stray_llama(sig: int = signal.SIGTERM) -> int:
    """Kill llama-server processes on our port that we lost the pidfile for (e.g. RUN dir wiped).
    Matches on the executable name + --port argument only, never on loose substrings."""
    n = 0
    proc = Path("/proc")
    if not proc.exists():
        return 0
    for d in proc.glob("[0-9]*"):
        try:
            args = [a for a in (d / "cmdline").read_bytes().decode(errors="replace").split("\0") if a]
        except OSError:
            continue
        if not args or int(d.name) == os.getpid():
            continue
        exe = args[1] if Path(args[0]).name.startswith("python") and len(args) > 1 else args[0]
        if Path(exe).name != "llama-server" or "--port" not in args:
            continue
        i = args.index("--port")
        if i + 1 < len(args) and args[i + 1] == str(LLAMA_PORT):
            with contextlib.suppress(OSError):
                os.kill(int(d.name), sig)
                n += 1
    return n


def stop_llama() -> None:
    stop_process("llama")
    if kill_stray_llama() and not wait_port_closed(LLAMA_HOST, LLAMA_PORT, 10):
        kill_stray_llama(signal.SIGKILL)
    if not wait_port_closed(LLAMA_HOST, LLAMA_PORT, 15):
        raise RuntimeError(f"Port {LLAMA_PORT} is still in use by something that is not our llama-server")


def tail_log(name: str, n: int = 20) -> str:
    try:
        return "\n".join((LOGS / f"{name}.log").read_text(errors="replace").splitlines()[-n:])
    except OSError:
        return "(no log)"


# ---------------------------------------------------------------------
# SYSTEM PACKAGES  (apt-get / apk / dnf / yum, root or sudo)
# ---------------------------------------------------------------------

SYS_TOOLS: Dict[str, Tuple[str, Dict[str, List[str]]]] = {
    "git": ("git", {"apt": ["git"], "apk": ["git"], "dnf": ["git"]}),
    "curl": ("curl", {"apt": ["curl", "ca-certificates"], "apk": ["curl", "ca-certificates"], "dnf": ["curl"]}),
    "cmake": ("cmake", {"apt": ["cmake"], "apk": ["cmake"], "dnf": ["cmake"]}),
    "compiler": ("g++", {"apt": ["build-essential"], "apk": ["build-base", "linux-headers"], "dnf": ["gcc-c++", "make"]}),
    "pkgconf": ("pkg-config", {"apt": ["pkg-config"], "apk": ["pkgconf"], "dnf": ["pkgconf-pkg-config"]}),
    "node": ("npm", {"apt": ["nodejs", "npm"], "apk": ["nodejs", "npm"], "dnf": ["nodejs", "npm"]}),
    "ffmpeg": ("ffmpeg", {"apt": ["ffmpeg"], "apk": ["ffmpeg"], "dnf": ["ffmpeg-free"]}),
    "pyvenv": ("__never_on_path__", {"apt": ["python3-venv"], "apk": ["py3-virtualenv"], "dnf": ["python3-virtualenv"]}),
}


def is_root() -> bool:
    return hasattr(os, "geteuid") and os.geteuid() == 0


def sudo_prefix() -> Optional[List[str]]:
    if is_root():
        return []
    if shutil.which("sudo"):
        return ["sudo", "-n"]
    return None


def detect_pm() -> Optional[str]:
    for pm in ("apt-get", "apk", "dnf", "yum"):
        if shutil.which(pm):
            return pm
    return None


_APT_UPDATED = False


def sys_install(names: List[str], *, required: bool = True) -> bool:
    global _APT_UPDATED
    missing = [n for n in names if not shutil.which(SYS_TOOLS[n][0])]
    if not missing:
        return True
    pm, pre = detect_pm(), sudo_prefix()
    problem = ""
    if not pm:
        problem = "no supported package manager (apt-get/apk/dnf/yum)"
    elif pre is None:
        problem = "not root and sudo is unavailable"
    if problem:
        msg = f"Missing {missing} but {problem}. Install them manually."
        if required:
            raise RuntimeError(msg)
        warn(msg)
        return False
    fam = {"apt-get": "apt", "apk": "apk", "dnf": "dnf", "yum": "dnf"}[pm]
    pkgs = sorted({p for n in missing for p in SYS_TOOLS[n][1].get(fam, [])})
    env = {"DEBIAN_FRONTEND": "noninteractive"}
    info(f"Installing via {pm}: {' '.join(pkgs)}")
    try:
        if pm == "apt-get":
            if not _APT_UPDATED:
                sh(pre + ["apt-get", "update", "-qq"], check=False, env=env)
                _APT_UPDATED = True
            sh(pre + ["apt-get", "install", "-y", "-qq", "--no-install-recommends", *pkgs], env=env)
        elif pm == "apk":
            sh(pre + ["apk", "add", "--no-cache", *pkgs])
        else:
            sh(pre + [pm, "install", "-y", *pkgs])
    except RuntimeError:
        if required:
            raise
        warn(f"Could not install {pkgs}")
        return False
    still = [n for n in missing if not shutil.which(SYS_TOOLS[n][0])]
    if still and required:
        raise RuntimeError(f"Still missing after install: {still}")
    return not still


# ---------------------------------------------------------------------
# GOOGLE DRIVE PERSISTENCE
# ---------------------------------------------------------------------


def safe_extract(tf: tarfile.TarFile, dest: Path, members: Optional[List[tarfile.TarInfo]] = None) -> None:
    try:
        tf.extractall(dest, members=members, filter="tar")
    except TypeError:  # Python < 3.11.4 has no extraction filters
        tf.extractall(dest, members=members)


def cache_file(name: str) -> Optional[Path]:
    return (PERSIST / "cache" / name) if PERSIST else None


def cache_save(name: str, rel_paths: List[str]) -> None:
    dest = cache_file(name)
    rels = [p for p in rel_paths if (ROOT / p).exists()]
    if not dest or not rels:
        return
    info(f"Saving {name} to Drive (one-time, can take a few minutes)...")
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".tmp")
    try:
        with tarfile.open(tmp, "w:gz", compresslevel=1) as tf:
            for p in rels:
                tf.add(ROOT / p, arcname=p)
        os.replace(tmp, dest)
        ok(f"Drive cache saved: {dest.name}")
    except Exception as e:
        warn(f"Drive cache save failed ({e}); continuing")
        with contextlib.suppress(OSError):
            tmp.unlink()


def cache_restore(name: str) -> bool:
    src = cache_file(name)
    if not src or not src.exists():
        return False
    info(f"Restoring {name} from Drive...")
    try:
        with tarfile.open(src, "r:gz") as tf:
            safe_extract(tf, ROOT)
        return True
    except Exception as e:
        warn(f"Drive cache restore failed: {e}")
        return False


_SYNC_SKIP = {"cache", "tmp", "__pycache__", ".cache"}


def _backup_sqlite(src: Path, dst: Path) -> None:
    tmp = dst.with_name(dst.name + ".tmp")
    s = sqlite3.connect(f"file:{src}?mode=ro", uri=True, timeout=30)
    d = sqlite3.connect(tmp)
    try:
        s.backup(d)
    finally:
        d.close()
        s.close()
    os.replace(tmp, dst)


def sync_state() -> int:
    """Snapshot ROOT/data (chat DB, hive DB, secrets, uploads) to Drive. Safe to call anytime."""
    if not PERSIST or not DATA.exists():
        return 0
    root, n = PERSIST / "state", 0
    for p in DATA.rglob("*"):
        try:
            rel = p.relative_to(DATA)
            if p.is_dir() or any(x in _SYNC_SKIP for x in rel.parts) or p.name.endswith(("-wal", "-shm", "-journal", ".tmp")):
                continue
            size = p.stat().st_size
            if size > 200 * 1024 * 1024:
                continue
            dst = root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            if p.suffix in (".db", ".sqlite", ".sqlite3"):
                _backup_sqlite(p, dst)
            elif not dst.exists() or dst.stat().st_size != size or dst.stat().st_mtime < p.stat().st_mtime:
                shutil.copy2(p, dst)
            n += 1
        except Exception as e:
            log.debug("sync skip %s: %s", p, e)
    return n


def restore_state() -> None:
    if not PERSIST or not (PERSIST / "state").exists():
        return
    if DB_PATH.exists() or (WEBUI_DATA / "webui.db").exists():
        return  # local data present; never overwrite it with an older snapshot
    info("Restoring chats/accounts/hive memory from Drive...")
    shutil.copytree(PERSIST / "state", DATA, dirs_exist_ok=True)
    ok("State restored")


# ---------------------------------------------------------------------
# PYTHON ENV (uv + Python 3.11 for Open WebUI), NODE, CLINE, NGROK
# ---------------------------------------------------------------------


def find_uv() -> Optional[str]:
    u = shutil.which("uv")
    if u:
        return u
    for c in (Path.home() / ".local/bin/uv", Path.home() / ".cargo/bin/uv", Path("/usr/local/bin/uv")):
        if c.exists():
            return str(c)
    return None


def install_uv() -> str:
    try:
        sh([sys.executable, "-m", "pip", "install", "-q", "uv"])
    except RuntimeError:
        sh("curl -LsSf https://astral.sh/uv/install.sh | sh")
    u = find_uv()
    if not u:
        raise RuntimeError("uv could not be installed")
    return u


def venv_ok() -> bool:
    py = VENV / "bin" / "python"
    if not py.exists():
        return False
    try:
        r = subprocess.run([str(py), "-c", "import importlib.util,sys;sys.exit(0 if importlib.util.find_spec('open_webui') else 1)"],
                           capture_output=True, timeout=90)
        return r.returncode == 0
    except Exception:
        return False


def _fallback_venv(pkgs: List[str]) -> None:
    if sys.version_info[:2] not in ((3, 11), (3, 12)):
        raise RuntimeError(f"uv unavailable and system Python {sys.version_info[0]}.{sys.version_info[1]} is not 3.11/3.12")
    try:
        sh([sys.executable, "-m", "venv", str(VENV)])
    except RuntimeError:
        sys_install(["pyvenv"])
        shutil.rmtree(VENV, ignore_errors=True)
        sh([sys.executable, "-m", "venv", str(VENV)])
    py = str(VENV / "bin" / "python")
    sh([py, "-m", "pip", "install", "-q", "--upgrade", "pip"])
    sh([py, "-m", "pip", "install", *pkgs])


def ensure_python_env() -> None:
    if venv_ok():
        return
    if cache_restore("venv.tgz") and venv_ok():
        return
    shutil.rmtree(VENV, ignore_errors=True)
    env = {"UV_PYTHON_INSTALL_DIR": str(PYDIR), "UV_LINK_MODE": "copy"}
    try:
        uv = find_uv() or install_uv()
        sh([uv, "venv", "--python", PY_VERSION, str(VENV)], env=env)
        sh([uv, "pip", "install", "--python", str(VENV / "bin" / "python"), OPENWEBUI_SPEC], env=env)
        if ENABLE_COMPUTER:
            try:
                sh([uv, "pip", "install", "--python", str(VENV / "bin" / "python"), "cptr"], env=env)
            except RuntimeError as e:
                warn(f"cptr install failed (Computer disabled): {e}")
    except RuntimeError as e:
        warn(f"uv route failed ({str(e)[:200]}); trying plain venv+pip")
        shutil.rmtree(VENV, ignore_errors=True)
        _fallback_venv([OPENWEBUI_SPEC] + (["cptr"] if ENABLE_COMPUTER else []))
    if not venv_ok():
        raise RuntimeError("Open WebUI is not importable after install")
    cache_save("venv.tgz", [".venv", "pythons"])


def _node_major() -> int:
    n = shutil.which("node")
    if not n:
        return 0
    r = subprocess.run([n, "--version"], capture_output=True, text=True)
    m = re.search(r"v(\d+)", r.stdout or "")
    return int(m.group(1)) if m else 0


def ensure_node() -> None:
    if _node_major() >= 20 and shutil.which("npm"):
        return
    pm = detect_pm()
    if pm == "apk":  # musl: official glibc tarballs won't run
        sys_install(["node"])
        return
    arch = {"x86_64": "x64", "amd64": "x64", "aarch64": "arm64", "arm64": "arm64"}.get(platform.machine().lower())
    if not arch:
        raise RuntimeError(f"No Node build for {platform.machine()}")
    code, idx = http_json("GET", "https://nodejs.org/dist/index.json", timeout=30)
    ver = next((e["version"] for e in (idx if isinstance(idx, list) else []) if e.get("version", "").startswith("v22.")), None)
    if not ver:
        raise RuntimeError("Could not resolve a Node 22 release")
    tgz = ROOT / f"node-{ver}.tar.xz"
    download(f"https://nodejs.org/dist/{ver}/node-{ver}-linux-{arch}.tar.xz", tgz)
    dest = BIN / "node"
    shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True)
    with tarfile.open(tgz, "r:xz") as tf:
        members = tf.getmembers()
        for m in members:
            m.name = "/".join(m.name.split("/")[1:])  # strip top-level dir
        safe_extract(tf, dest, [m for m in members if m.name])
    tgz.unlink(missing_ok=True)
    os.environ["PATH"] = f"{dest / 'bin'}{os.pathsep}{os.environ['PATH']}"


def cline_path() -> Optional[str]:
    os.environ["PATH"] = f"{NPM_PREFIX / 'bin'}{os.pathsep}{os.environ['PATH']}"
    return shutil.which("cline")


def ensure_cline() -> str:
    c = cline_path()
    if c:
        return c
    ensure_node()
    NPM_PREFIX.mkdir(parents=True, exist_ok=True)
    sh(["npm", "install", "-g", "cline", "--prefix", str(NPM_PREFIX)])
    c = cline_path()
    if not c:
        raise RuntimeError("Cline installed but not on PATH")
    return c


def configure_cline(cline: str) -> bool:
    """Non-interactive: point Cline at the local Sovereign gateway (no login, no input())."""
    r = sh([cline, "auth", "-p", "openai", "-k", api_key(), "-b", api_url("/v1"), "-m", MODEL_IDS["coder"]],
           check=False, capture=True, timeout=90, quiet=True)
    return r.returncode == 0


NGROK_TGZ = {
    "x86_64": "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz",
    "aarch64": "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-arm64.tgz",
}


def ngrok_bin() -> str:
    return shutil.which("ngrok") or str(BIN / "ngrok")


def _ngrok_works(path: str) -> bool:
    try:
        return subprocess.run([path, "version"], capture_output=True, timeout=30).returncode == 0
    except Exception:
        return False


def ensure_ngrok() -> str:
    b = ngrok_bin()
    if Path(b).exists() and _ngrok_works(b):
        return b
    cached = cache_file("ngrok")
    if cached and cached.exists():
        shutil.copy2(cached, BIN / "ngrok")
        os.chmod(BIN / "ngrok", 0o755)
        if _ngrok_works(str(BIN / "ngrok")):
            return str(BIN / "ngrok")
    errors: List[str] = []
    # Option 1: official tarball
    url = NGROK_TGZ.get(platform.machine().lower())
    if url:
        try:
            tgz = RUN / "ngrok.tgz"
            download(url, tgz)
            with tarfile.open(tgz, "r:gz") as tf:
                tf.extract("ngrok", BIN)
            os.chmod(BIN / "ngrok", 0o755)
            tgz.unlink(missing_ok=True)
        except Exception as e:
            errors.append(f"tarball: {e}")
    # Option 2: pyngrok downloads the agent itself
    if not _ngrok_works(str(BIN / "ngrok")):
        try:
            sh([sys.executable, "-m", "pip", "install", "-q", "pyngrok"])
            code = "from pyngrok import conf,ngrok;ngrok.install_ngrok();print(conf.get_default().ngrok_path)"
            r = sh([sys.executable, "-c", code], capture=True)
            p = (r.stdout or "").strip().splitlines()[-1]
            if p and Path(p).exists():
                shutil.copy2(p, BIN / "ngrok")
                os.chmod(BIN / "ngrok", 0o755)
        except Exception as e:
            errors.append(f"pyngrok: {e}")
    # Option 3: ngrok apt repository (root/sudo + apt only)
    if not _ngrok_works(str(BIN / "ngrok")) and shutil.which("apt-get") and sudo_prefix() is not None:
        try:
            pre = " ".join(sudo_prefix())
            sh(f"curl -fsSL https://ngrok-agent.s3.amazonaws.com/ngrok.asc | {pre} tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null "
               f"&& echo 'deb https://ngrok-agent.s3.amazonaws.com buster main' | {pre} tee /etc/apt/sources.list.d/ngrok.list "
               f"&& {pre} apt-get update -qq && {pre} apt-get install -y -qq ngrok")
        except Exception as e:
            errors.append(f"apt: {e}")
    b = str(BIN / "ngrok") if _ngrok_works(str(BIN / "ngrok")) else (shutil.which("ngrok") or "")
    if not b or not _ngrok_works(b):
        raise RuntimeError("ngrok could not be installed. " + " | ".join(errors))
    if PERSIST and b:
        with contextlib.suppress(Exception):
            (PERSIST / "cache").mkdir(parents=True, exist_ok=True)
            shutil.copy2(b, PERSIST / "cache" / "ngrok")
    return b


# ---------------------------------------------------------------------
# LLAMA.CPP  (CUDA when available, Drive-cached binary)
# ---------------------------------------------------------------------

_GPU: Optional[Dict[str, Any]] = None


def gpu_info() -> Dict[str, Any]:
    global _GPU
    if _GPU is not None:
        return _GPU
    g: Dict[str, Any] = {"nvidia": False, "name": "", "cap": ""}
    if shutil.which("nvidia-smi"):
        for q in ("name,compute_cap", "name"):
            try:
                r = subprocess.run(["nvidia-smi", f"--query-gpu={q}", "--format=csv,noheader"],
                                   capture_output=True, text=True, timeout=20)
            except Exception:
                continue
            if r.returncode == 0 and r.stdout.strip():
                first = r.stdout.strip().splitlines()[0]
                name, _, cap = first.partition(",")
                g = {"nvidia": True, "name": name.strip(), "cap": cap.strip().replace(".", "")}
                break
    _GPU = g
    return g


def find_nvcc() -> Optional[str]:
    n = shutil.which("nvcc")
    if n:
        return n
    for c in sorted(Path("/usr/local").glob("cuda*/bin/nvcc"), reverse=True):
        return str(c)
    return None


def llama_env() -> Dict[str, str]:
    ld = os.environ.get("LD_LIBRARY_PATH", "")
    return {"LD_LIBRARY_PATH": f"{LLAMA_BIN_DIR}{os.pathsep}{ld}" if ld else str(LLAMA_BIN_DIR)}


def llama_works() -> bool:
    if not LLAMA_SERVER.exists():
        return False
    try:
        r = subprocess.run([str(LLAMA_SERVER), "--version"], capture_output=True, timeout=60,
                           env={**os.environ, **llama_env()})
        return r.returncode == 0
    except Exception:
        return False


def llama_cache_name() -> str:
    cpu = ""
    with contextlib.suppress(Exception):
        txt = Path("/proc/cpuinfo").read_text()
        m, f = re.search(r"model name\s*:\s*(.*)", txt), re.search(r"flags\s*:\s*(.*)", txt)
        cpu = (m.group(1) if m else "") + (f.group(1) if f else "")
    g = gpu_info()
    key = hashlib.sha1(f"{cpu}|{g['name']}|{g['cap']}|{platform.machine()}".encode()).hexdigest()[:10]
    return f"llama-{key}.tgz"


def build_llama() -> None:
    sys_install(["git", "cmake", "compiler", "pkgconf", "curl"])
    if not (LLAMA_SRC / ".git").exists():
        shutil.rmtree(LLAMA_SRC, ignore_errors=True)
        sh(["git", "clone", "--depth", "1", "https://github.com/ggml-org/llama.cpp.git", str(LLAMA_SRC)])
    build = LLAMA_SRC / "build"
    args = ["cmake", "-S", LLAMA_SRC, "-B", build, "-DCMAKE_BUILD_TYPE=Release", "-DGGML_NATIVE=ON",
            "-DLLAMA_CURL=OFF", "-DLLAMA_BUILD_TESTS=OFF"]
    g, nvcc = gpu_info(), find_nvcc()
    if g["nvidia"] and nvcc:
        args += ["-DGGML_CUDA=ON", f"-DCMAKE_CUDA_COMPILER={nvcc}"]
        if g["cap"]:
            args.append(f"-DCMAKE_CUDA_ARCHITECTURES={g['cap']}")
        os.environ["PATH"] = f"{Path(nvcc).parent}{os.pathsep}{os.environ['PATH']}"
        info(f"CUDA build for {g['name']} (arch {g['cap'] or 'default'}). Expect 10-25 min on Colab's 2 CPU cores.")
    else:
        if g["nvidia"]:
            warn("GPU present but nvcc not found -> CPU-only build")
        info("CPU build")
    sh(args)
    sh(["cmake", "--build", build, "--config", "Release", "--target", "llama-server", "-j", str(os.cpu_count() or 2)])
    if not LLAMA_SERVER.exists():
        found = list(LLAMA_SRC.glob("build/**/llama-server"))
        if not found:
            raise RuntimeError("llama-server binary was not produced")
        raise RuntimeError(f"llama-server built at unexpected path: {found[0]} (set SOVEREIGN_LLAMA_SERVER)")


def ensure_llama() -> None:
    if llama_works():
        return
    name = llama_cache_name()
    if LLAMA_SERVER.is_relative_to(ROOT):
        rel = str(LLAMA_BIN_DIR.relative_to(ROOT))
        if cache_restore(name) and llama_works():
            ok("llama.cpp restored from Drive cache")
            return
        build_llama()
        if not llama_works():
            raise RuntimeError("llama-server built but does not run (--version failed)")
        cache_save(name, [rel])
    else:
        raise RuntimeError(f"SOVEREIGN_LLAMA_SERVER does not run: {LLAMA_SERVER}")


# ---------------------------------------------------------------------
# MODELS  (HF file discovery + resumable curl download, Drive master copy)
# ---------------------------------------------------------------------


def hf_list(repo: str) -> List[str]:
    h = {"Authorization": f"Bearer {HF_TOKEN}"} if HF_TOKEN else {}
    code, data = http_json("GET", f"https://huggingface.co/api/models/{repo}", headers=h, timeout=30)
    if code != 200 or not isinstance(data, dict):
        raise RuntimeError(f"Cannot list Hugging Face repo {repo} (HTTP {code}). Set SOVEREIGN_*_FILE to skip listing.")
    return [s["rfilename"] for s in data.get("siblings", [])]


def pick_gguf(files: List[str], quant: str, fallbacks: List[str]) -> str:
    ggufs = [f for f in files if f.lower().endswith(".gguf") and "mmproj" not in f.lower()
             and not re.search(r"-\d{5}-of-\d{5}", f)]

    def has(f: str, q: str) -> bool:
        return re.search(rf"(?<![a-z0-9]){re.escape(q)}(?![a-z0-9])", f.lower()) is not None

    for q in [quant, *fallbacks]:
        for f in ggufs:
            if has(f, q):  # (?<![a-z0-9]) keeps bf16 from matching f16
                return f
    if ggufs:
        return sorted(ggufs, key=len)[0]
    raise RuntimeError("No single-file GGUF found in repo")


def _meta_path(p: Path) -> Path:
    return p.with_name(p.name + ".json")


def _meta_ok(p: Path, repo: str, explicit: str) -> bool:
    if not p.exists() or p.stat().st_size < 10_000_000:
        return False
    mp = _meta_path(p)
    if not mp.exists():
        return True  # model from an earlier script version; accept and adopt
    try:
        m = json.loads(mp.read_text())
        return m.get("repo") == repo and (not explicit or m.get("file") == explicit)
    except Exception:
        return False


def _copy_big(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + ".tmp")
    info(f"Copying {src.name} ({src.stat().st_size / 1e9:.1f} GB) -> {dst.parent}")
    shutil.copyfile(src, tmp)
    os.replace(tmp, dst)
    if _meta_path(src).exists():
        shutil.copyfile(_meta_path(src), _meta_path(dst))


def ensure_model(name: str, repo: str, explicit: str, quant: str, fallbacks: List[str]) -> Path:
    local = MODELS / f"{name}.gguf"
    master = (PERSIST / "models" / f"{name}.gguf") if PERSIST else None
    if _meta_ok(local, repo, explicit):
        return local
    if master and _meta_ok(master, repo, explicit):
        _copy_big(master, local)
        return local
    free = shutil.disk_usage(ROOT).free / 1e9
    if free < 12:
        warn(f"Only {free:.1f} GB free on the runtime disk")
    filename = explicit or pick_gguf(hf_list(repo), quant, fallbacks)
    info(f"Downloading {repo} :: {filename}")
    target = master or local
    download(f"https://huggingface.co/{repo}/resolve/main/{urllib.parse.quote(filename)}", target, HF_TOKEN)
    _meta_path(target).write_text(json.dumps({"repo": repo, "file": filename}))
    if target != local:
        _copy_big(target, local)
    return local


def ensure_models() -> None:
    ensure_model("reasoning", REASONING_REPO, REASONING_FILE, REASONING_QUANT, ["q8_0", "f16", "q6_k", "q5_k_m", "q4_k_m"])
    ensure_model("coder", CODER_REPO, CODER_FILE, CODER_QUANT, ["q5_k_m", "q4_k_s", "q5_k_s", "q6_k", "q8_0"])


# ---------------------------------------------------------------------
# SQLITE + HIVE + RAG   (runs inside the gateway process)
# ---------------------------------------------------------------------

DB_LOCK = threading.RLock()


def dbx(sql: str, params: Any = (), *, many: bool = False, fetch: bool = False) -> Any:
    with DB_LOCK:
        c = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
        c.row_factory = sqlite3.Row
        try:
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA busy_timeout=30000")
            cur = c.executemany(sql, params) if many else c.execute(sql, params)
            rows = [dict(r) for r in cur.fetchall()] if fetch else None
            c.commit()
            return rows if fetch else cur.lastrowid
        finally:
            c.close()


def db_init() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    with DB_LOCK:
        c = sqlite3.connect(DB_PATH, timeout=30)
        try:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, kind TEXT, payload TEXT);
            CREATE TABLE IF NOT EXISTS agents(id TEXT PRIMARY KEY, tier TEXT, role TEXT, state TEXT, heartbeat REAL,
                tasks INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS agent_messages(id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, sender TEXT,
                receiver TEXT, message TEXT);
            CREATE TABLE IF NOT EXISTS agent_relationships(a TEXT, b TEXT, strength REAL DEFAULT 0.5,
                collabs INTEGER DEFAULT 0, updated REAL, PRIMARY KEY(a,b));
            CREATE TABLE IF NOT EXISTS documents(id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, source TEXT, title TEXT,
                content TEXT);
            CREATE TABLE IF NOT EXISTS chunks(id INTEGER PRIMARY KEY AUTOINCREMENT, doc_id INTEGER, idx INTEGER,
                content TEXT, tokens TEXT);
            CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, kind TEXT, status TEXT, meta TEXT);
            CREATE INDEX IF NOT EXISTS idx_msg_recv ON agent_messages(receiver, ts);
            CREATE INDEX IF NOT EXISTS idx_msg_send ON agent_messages(sender, ts);
            CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id);
            """)
            c.commit()
        finally:
            c.close()


def event(kind: str, payload: Any = None) -> None:
    with contextlib.suppress(Exception):
        dbx("INSERT INTO events(ts,kind,payload) VALUES(?,?,?)", (time.time(), kind, json.dumps(payload, default=str)))


ELITE_ROLES = ["architect", "reasoner", "coder", "researcher", "planner", "reviewer", "debugger",
               "security-reviewer", "rag-specialist", "tool-router"]
SUPPORT_ROLES = ["collector", "summarizer", "tester", "indexer", "formatter", "observer", "memory-worker",
                 "search-worker", "utility-worker", "validator"]
ROUTES = [
    ("debugger", ("debug", "traceback", "stack trace", "exception", "bug", "fix this")),
    ("security-reviewer", ("security", "vulnerab", "exploit", "pentest", "audit", "harden", "ctf")),
    ("coder", ("code", "python", "javascript", "typescript", "function", "refactor", "script", "bash", "docker", "sql", "api")),
    ("researcher", ("research", "search", "find", "latest", "investigate", "compare")),
    ("planner", ("plan", "roadmap", "steps", "schedule", "strategy")),
    ("architect", ("architecture", "design", "system")),
    ("rag-specialist", ("document", "rag", "knowledge", "index")),
]
CODER_ROLES = {"coder", "debugger", "security-reviewer", "tool-router"}


class Hive:
    def __init__(self) -> None:
        self.agents: List[Dict[str, str]] = []
        self.by_role: Dict[str, List[Dict[str, str]]] = {}
        self.rr: Dict[str, int] = {}
        self.lock = threading.Lock()
        for i in range(NUM_ELITE):
            self._add(f"elite-{i + 1:04d}", "elite", ELITE_ROLES[i % len(ELITE_ROLES)])
        for i in range(NUM_SUPPORT):
            self._add(f"support-{i + 1:04d}", "support", SUPPORT_ROLES[i % len(SUPPORT_ROLES)])

    def _add(self, aid: str, tier: str, role: str) -> None:
        a = {"id": aid, "tier": tier, "role": role}
        self.agents.append(a)
        self.by_role.setdefault(role, []).append(a)

    def persist(self) -> None:
        have = {r["id"] for r in dbx("SELECT id FROM agents", fetch=True)}
        rows = [(a["id"], a["tier"], a["role"], "online", time.time()) for a in self.agents if a["id"] not in have]
        if rows:
            dbx("INSERT OR IGNORE INTO agents(id,tier,role,state,heartbeat) VALUES(?,?,?,?,?)", rows, many=True)

    def role_for(self, task: str) -> str:
        t = task.lower()
        for role, words in ROUTES:
            if any(w in t for w in words):
                return role
        return "reasoner"

    def route(self, task: str) -> Dict[str, str]:
        role = self.role_for(task)
        with self.lock:
            i = self.rr.get(role, 0)
            self.rr[role] = i + 1
            agent = self.by_role[role][i % len(self.by_role[role])]
        with contextlib.suppress(Exception):
            dbx("UPDATE agents SET tasks=tasks+1 WHERE id=?", (agent["id"],))
        return agent

    def route_model(self, task: str) -> str:
        return "coder" if self.role_for(task) in CODER_ROLES else "reasoning"

    def gossip_once(self, pairs: int = GOSSIP_PAIRS) -> None:
        now, msgs, rels = time.time(), [], []
        for _ in range(pairs):
            a, b = random.sample(self.agents, 2)
            msgs.append((now, a["id"], b["id"], f"[gossip] {a['role']} -> {b['role']} status sync"))
            rels.append((a["id"], b["id"], now))
        with DB_LOCK:
            c = sqlite3.connect(DB_PATH, timeout=30)
            try:
                c.executemany("INSERT INTO agent_messages(ts,sender,receiver,message) VALUES(?,?,?,?)", msgs)
                c.executemany("""INSERT INTO agent_relationships(a,b,strength,collabs,updated) VALUES(?,?,0.5,1,?)
                    ON CONFLICT(a,b) DO UPDATE SET strength=MIN(1.0,strength+0.02),collabs=collabs+1,updated=excluded.updated""", rels)
                c.commit()
            finally:
                c.close()

    def heartbeat_once(self) -> None:
        dbx("UPDATE agents SET heartbeat=?, state='online'", (time.time(),))

    def status(self) -> Dict[str, Any]:
        msgs = dbx("SELECT COUNT(*) n FROM agent_messages", fetch=True)[0]["n"]
        online = dbx("SELECT COUNT(*) n FROM agents WHERE state='online' AND heartbeat>?", (time.time() - 5 * HEALTH_INTERVAL,), fetch=True)[0]["n"]
        tasks = dbx("SELECT COALESCE(SUM(tasks),0) n FROM agents", fetch=True)[0]["n"]
        return {"total": len(self.agents), "elite": NUM_ELITE, "support": NUM_SUPPORT, "online": online,
                "tasks_routed": tasks, "eternal_messages": msgs}


HIVE: Optional[Hive] = None


def hive_threads(stop: threading.Event) -> None:
    def loop(fn: Callable[[], None], every: float, label: str) -> None:
        while not stop.wait(every):
            try:
                fn()
            except Exception:
                log.exception("%s failed", label)

    assert HIVE is not None
    threading.Thread(target=loop, args=(HIVE.gossip_once, GOSSIP_INTERVAL, "gossip"), daemon=True).start()
    threading.Thread(target=loop, args=(HIVE.heartbeat_once, HEALTH_INTERVAL, "heartbeat"), daemon=True).start()


_WORD = re.compile(r"[A-Za-z0-9_]+")


def _tokens(text: str) -> List[str]:
    return [w.lower() for w in _WORD.findall(text)]


def rag_add(source: str, title: str, content: str, size: int = 1800, overlap: int = 250) -> int:
    doc_id = dbx("INSERT INTO documents(ts,source,title,content) VALUES(?,?,?,?)", (time.time(), source, title, content))
    rows, i, idx = [], 0, 0
    while i < len(content):
        chunk = content[i:i + size]
        rows.append((doc_id, idx, chunk, " ".join(sorted(set(_tokens(chunk))))))
        idx += 1
        if i + size >= len(content):
            break
        i += size - overlap
    if rows:
        dbx("INSERT INTO chunks(doc_id,idx,content,tokens) VALUES(?,?,?,?)", rows, many=True)
    return int(doc_id)


def rag_search(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    q = set(_tokens(query))
    if not q:
        return []
    rows = dbx("""SELECT c.content, d.title, d.source, c.tokens FROM chunks c JOIN documents d ON d.id=c.doc_id
                  ORDER BY c.id DESC LIMIT 5000""", fetch=True)
    scored = []
    for r in rows:
        ov = len(q & set(r["tokens"].split()))
        if ov:
            scored.append((ov / len(q), {"score": round(ov / len(q), 3), "title": r["title"], "source": r["source"],
                                          "content": r["content"]}))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [s[1] for s in scored[:limit]]


# ---------------------------------------------------------------------
# MODEL MANAGER  (owns llama-server; ONE resident model; hot-swap)
# ---------------------------------------------------------------------


def llama_cmd(model: Path, name: str, minimal: bool) -> List[str]:
    ngl = _env("LLAMA_GPU_LAYERS", default="99" if gpu_info()["nvidia"] else "0")
    cmd = [str(LLAMA_SERVER), "-m", str(model), "--host", LLAMA_HOST, "--port", str(LLAMA_PORT),
           "-c", str(LLAMA_CTX), "-ngl", ngl]
    if not minimal:  # newer flags; if this build rejects them we retry with the minimal set
        cmd += ["--jinja", "--reasoning-format", "deepseek", "--metrics"]
    return cmd


def wait_llama_ready(proc: subprocess.Popen, timeout: float) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if proc.poll() is not None:
            return False
        if http_ok(f"http://{LLAMA_HOST}:{LLAMA_PORT}/health", 3):
            return True
        time.sleep(1)
    return False


class ModelManager:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.name: Optional[str] = None
        self.error = ""

    def healthy(self) -> bool:
        return http_ok(f"http://{LLAMA_HOST}:{LLAMA_PORT}/health", 2)

    def ensure(self, name: str) -> None:
        with self.lock:
            if self.name == name and self.healthy():
                return
            self._start(name)

    def _start(self, name: str) -> None:
        model = MODELS / f"{name}.gguf"
        if not model.exists():
            raise RuntimeError(f"Model file missing: {model}")
        if not LLAMA_SERVER.exists():
            raise RuntimeError(f"llama-server missing: {LLAMA_SERVER}")
        stop_llama()
        self.name = None
        for minimal in (False, True):
            t0 = time.time()
            proc = spawn("llama", llama_cmd(model, name, minimal), cwd=LLAMA_BIN_DIR, env=llama_env())
            if wait_llama_ready(proc, STARTUP_TIMEOUT):
                self.name, self.error = name, ""
                log.info("Resident model: %s (%s flags)", name, "minimal" if minimal else "full")
                event("model_switched", {"model": name})
                return
            died_fast = proc.poll() is not None and time.time() - t0 < 90
            stop_process("llama")
            if not died_fast:
                break
        self.error = tail_log("llama", 12)
        raise RuntimeError(f"llama-server failed to start for '{name}':\n{self.error}")

    def status(self) -> Dict[str, Any]:
        return {"model": self.name, "up": self.healthy(), "error": self.error[-300:]}


MM = ModelManager()
GEN_LOCK = threading.Lock()  # one generation at a time (single resident model)


# ---------------------------------------------------------------------
# GATEWAY  (stdlib HTTP server: OpenAI-compatible, streaming, RAG, hive)
# ---------------------------------------------------------------------

DASHBOARD = """<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Sovereign Hive</title><body style="margin:0;background:#0d0f12;color:#eee;font-family:system-ui;padding:24px">
<h1>Sovereign Hive</h1><div id=c style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px"></div>
<script>async function r(){try{const h=await (await fetch('/health')).json();const hv=h.hive||{};
const card=(t,v)=>`<div style="background:#171a20;border:1px solid #30343d;border-radius:12px;padding:16px"><div style="opacity:.6;font-size:12px">${t}</div><div style="font-size:26px;color:#4ade80">${v}</div></div>`;
c.innerHTML=card('Model',h.llama.model||'loading')+card('llama up',h.llama.up)+card('Agents online',(hv.online||0)+'/'+(hv.total||0))+card('Eternal messages',(hv.eternal_messages||0).toLocaleString())}catch(e){c.textContent=e}}
r();setInterval(r,4000)</script>"""

_API_KEY = ""


def _last_user_text(messages: List[Dict[str, Any]]) -> str:
    for m in reversed(messages):
        if m.get("role") == "user":
            c = m.get("content", "")
            if isinstance(c, list):
                return " ".join(p.get("text", "") for p in c if isinstance(p, dict))
            return str(c)
    return ""


def pick_role(model: str, messages: List[Dict[str, Any]]) -> str:
    m = (model or "").lower()
    if "coder" in m:
        return "coder"
    if "auto" in m and HIVE:
        return HIVE.route_model(_last_user_text(messages))
    return "reasoning"


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "SovereignGateway/4"

    def log_message(self, fmt: str, *args: Any) -> None:
        log.debug("%s - %s", self.address_string(), fmt % args)

    # ---- helpers ----
    def _send(self, code: int, obj: Any = None, raw: Optional[bytes] = None, ctype: str = "application/json",
              extra: Optional[Dict[str, str]] = None) -> None:
        body = raw if raw is not None else json.dumps(obj, ensure_ascii=False, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def _err(self, code: int, msg: str) -> None:
        self._send(code, {"error": {"message": msg, "code": code}})

    def _auth(self) -> bool:
        got = self.headers.get("Authorization", "").encode()
        if secrets.compare_digest(got, f"Bearer {_API_KEY}".encode()):
            return True
        self._err(401, "invalid or missing API key")
        return False

    def _body(self) -> Dict[str, Any]:
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b"{}"
        return json.loads(raw or b"{}")

    # ---- routing ----
    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def _dispatch(self, method: str) -> None:
        u = urllib.parse.urlparse(self.path)
        path, qs = u.path.rstrip("/") or "/", urllib.parse.parse_qs(u.query)
        q = lambda k, d="": (qs.get(k) or [d])[0]  # noqa: E731
        try:
            if method == "GET" and path == "/health":
                return self._send(200, {"status": "ok", "time": time.time(), "llama": MM.status(),
                                        "hive": HIVE.status() if HIVE else None, "root": str(ROOT)})
            if method == "GET" and path in ("/", "/admin/dashboard"):
                return self._send(200, raw=DASHBOARD.encode(), ctype="text/html; charset=utf-8")
            if not self._auth():
                return
            if method == "GET" and path == "/v1/models":
                return self._send(200, {"object": "list", "data": [
                    {"id": v, "object": "model", "owned_by": "sovereign"} for v in MODEL_IDS.values()]})
            if method == "POST" and path == "/v1/chat/completions":
                return self._chat()
            if method == "POST" and path == "/v1/rag/documents":
                b = self._body()
                return self._send(200, {"id": rag_add(b.get("source", "manual"), b.get("title", "Untitled"), b.get("content", "")),
                                        "status": "stored"})
            if method == "GET" and path == "/v1/rag/search":
                return self._send(200, {"query": q("q"), "results": rag_search(q("q"), int(q("limit", "5")))})
            if path.startswith("/hive/") and HIVE is None:
                return self._err(503, "hive not ready")
            if method == "GET" and path == "/hive/status":
                return self._send(200, HIVE.status())
            if method == "GET" and path == "/hive/route":
                a = HIVE.route(q("task"))
                return self._send(200, {"agent": a, "model": HIVE.route_model(q("task"))})
            if method == "GET" and path == "/hive/agents":
                s, l = int(q("skip", "0")), max(1, min(int(q("limit", "50")), 500))
                return self._send(200, {"agents": dbx("SELECT * FROM agents ORDER BY id LIMIT ? OFFSET ?", (l, s), fetch=True),
                                        "total": len(HIVE.agents), "skip": s, "limit": l})
            m = re.fullmatch(r"/hive/agent/([\w-]+)/(memory|eternal-memory)", path)
            if method == "GET" and m:
                aid, kind = m.group(1), m.group(2)
                if aid not in {a["id"] for a in HIVE.agents}:
                    return self._err(404, "agent not found")
                sql = "SELECT ts,sender,receiver,message FROM agent_messages WHERE (sender=? OR receiver=? OR receiver='*')"
                if kind == "memory":
                    hrs = float(q("lookback_hours", "24"))
                    rows = dbx(sql + " AND ts>? ORDER BY ts DESC LIMIT 100", (aid, aid, time.time() - hrs * 3600), fetch=True)
                    return self._send(200, {"agent": aid, "messages": rows, "total": len(rows)})
                cnt = dbx("SELECT COUNT(*) n, MIN(ts) a, MAX(ts) b FROM agent_messages WHERE sender=? OR receiver=? OR receiver='*'",
                          (aid, aid), fetch=True)[0]
                rows = dbx(sql + " ORDER BY ts DESC LIMIT 10", (aid, aid), fetch=True)
                return self._send(200, {"agent": aid, "total_memories": cnt["n"], "earliest": cnt["a"], "latest": cnt["b"], "sample": rows})
            if method == "POST" and path == "/hive/broadcast":
                msg = str(self._body().get("message", "")).strip()
                if not msg:
                    return self._err(400, "no message")
                dbx("INSERT INTO agent_messages(ts,sender,receiver,message) VALUES(?,?,?,?)", (time.time(), "elite-0001", "*", f"[BROADCAST] {msg}"))
                return self._send(200, {"status": "broadcast", "recipients": len(HIVE.agents)})
            m = re.fullmatch(r"/hive/agent/([\w-]+)/collaborate/([\w-]+)", path)
            if method == "POST" and m:
                ids = {a["id"] for a in HIVE.agents}
                a, b = m.group(1), m.group(2)
                task = str(self._body().get("task", "")).strip()
                if a not in ids or b not in ids:
                    return self._err(404, "agent not found")
                if not task:
                    return self._err(400, "no task")
                dbx("INSERT INTO agent_messages(ts,sender,receiver,message) VALUES(?,?,?,?)", (time.time(), a, b, f"[COLLAB] {task}"))
                dbx("""INSERT INTO agent_relationships(a,b,strength,collabs,updated) VALUES(?,?,0.5,1,?)
                       ON CONFLICT(a,b) DO UPDATE SET strength=MIN(1.0,strength+0.05),collabs=collabs+1,updated=excluded.updated""",
                    (a, b, time.time()))
                return self._send(200, {"status": "collaboration_initiated", "agents": [a, b]})
            if path == "/admin/tasks":
                if method == "POST":
                    b = self._body()
                    tid = dbx("INSERT INTO tasks(ts,kind,status,meta) VALUES(?,?,?,?)",
                              (time.time(), b.get("kind", "generic"), "queued", json.dumps(b.get("metadata", {}))))
                    return self._send(200, {"task_id": tid, "status": "queued"})
                return self._send(200, dbx("SELECT * FROM tasks ORDER BY id DESC LIMIT ?", (max(1, min(int(q("limit", "50")), 500)),), fetch=True))
            return self._err(404, f"no route: {method} {path}")
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception as e:
            log.exception("handler error")
            with contextlib.suppress(Exception):
                self._err(500, f"{type(e).__name__}: {e}")

    # ---- chat completions (sync + SSE streaming, lock always released) ----
    def _chat(self) -> None:
        req = self._body()
        messages = req.get("messages") or []
        role = pick_role(req.get("model", ""), messages)
        text = _last_user_text(messages)
        use_rag, top_k = bool(req.pop("use_rag", False)), int(req.pop("rag_top_k", 5) or 5)
        req.pop("web_search", None)
        if use_rag and text:
            hits = rag_search(text, max(1, min(top_k, 8)))
            if hits:
                ctx = "LOCAL KNOWLEDGE (use when relevant, do not invent citations):\n" + "\n\n".join(
                    f"[{h['title']}] {h['content']}" for h in hits)[:12000]
                messages = [{"role": "system", "content": ctx}] + list(messages)
        payload = {**req, "messages": messages, "model": MODEL_IDS[role]}
        stream = bool(payload.get("stream"))
        agent = HIVE.route(text) if HIVE else {"id": "n/a"}
        extra = {"X-Hive-Agent": agent["id"], "X-Resident-Model": MODEL_IDS[role]}

        if not GEN_LOCK.acquire(timeout=REQUEST_TIMEOUT):
            return self._err(503, "gateway busy")
        conn: Optional[http.client.HTTPConnection] = None
        headers_sent = False
        try:
            MM.ensure(role)
            conn = http.client.HTTPConnection(LLAMA_HOST, LLAMA_PORT, timeout=REQUEST_TIMEOUT)
            conn.request("POST", "/v1/chat/completions", body=json.dumps(payload),
                         headers={"Content-Type": "application/json"})
            resp = conn.getresponse()
            if resp.status >= 400:
                return self._err(502, f"llama-server {resp.status}: {resp.read()[:400].decode(errors='replace')}")
            if not stream:
                return self._send(200, raw=resp.read(), extra=extra)
            self.send_response(200)
            for k, v in {"Content-Type": "text/event-stream", "Cache-Control": "no-cache", "Transfer-Encoding": "chunked",
                         "X-Accel-Buffering": "no", "Connection": "close", **extra}.items():
                self.send_header(k, v)
            self.end_headers()
            headers_sent = True
            while True:
                chunk = resp.read1(8192)
                if not chunk:
                    break
                self.wfile.write(b"%x\r\n%s\r\n" % (len(chunk), chunk))
                self.wfile.flush()
            self.wfile.write(b"0\r\n\r\n")
            self.close_connection = True
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True
        except Exception as e:
            log.exception("chat failed")
            if not headers_sent:
                with contextlib.suppress(Exception):
                    self._err(502, f"inference failure: {e}")
            self.close_connection = True
        finally:
            if conn:
                with contextlib.suppress(Exception):
                    conn.close()
            GEN_LOCK.release()


def serve_api() -> None:
    global HIVE, _API_KEY
    prepare_dirs()
    db_init()
    _API_KEY = api_key()
    stop = threading.Event()
    HIVE = Hive()
    HIVE.persist()
    hive_threads(stop)
    log.info("Hive online: %d agents", len(HIVE.agents))

    def boot_model() -> None:  # runs in background so the port opens instantly
        with contextlib.suppress(Exception):
            stop_llama()  # kill any stale llama left by a previous gateway
        try:
            MM.ensure("reasoning")
        except Exception:
            log.exception("initial model start failed (watchdog will retry)")

    def watchdog() -> None:
        while not stop.wait(30):
            if MM.name and not GEN_LOCK.locked() and not MM.healthy():
                log.warning("llama-server unhealthy; restarting %s", MM.name)
                try:
                    MM.ensure(MM.name)
                except Exception:
                    log.exception("watchdog restart failed")
            elif MM.name is None and not GEN_LOCK.locked():
                with contextlib.suppress(Exception):
                    MM.ensure("reasoning")

    threading.Thread(target=boot_model, daemon=True).start()
    threading.Thread(target=watchdog, daemon=True).start()
    srv = ThreadingHTTPServer((API_HOST, API_PORT), Handler)
    srv.daemon_threads = True
    signal.signal(signal.SIGTERM, lambda *_: threading.Thread(target=srv.shutdown, daemon=True).start())
    log.info("Sovereign gateway listening on http://%s:%d", API_HOST, API_PORT)
    try:
        srv.serve_forever()
    finally:
        stop.set()


# ---------------------------------------------------------------------
# SERVICE SPECS + SUPERVISOR  (restarts anything that dies, backoff, Drive sync)
# ---------------------------------------------------------------------


def self_path() -> Path:
    return SELF if SELF.exists() else Path(__file__).resolve()


def webui_env() -> Dict[str, str]:
    return {
        "DATA_DIR": str(WEBUI_DATA),
        "OPENAI_API_BASE_URLS": api_url("/v1"),
        "OPENAI_API_KEYS": api_key(),
        "ENABLE_OLLAMA_API": "false",
        "WEBUI_AUTH": "true",
        "DEFAULT_USER_ROLE": "pending",
        "WEBUI_SECRET_KEY": _secret("webui_secret", "WEBUI_SECRET_KEY"),
        "ANONYMIZED_TELEMETRY": "false",
        "SCARF_NO_ANALYTICS": "true",
        "DO_NOT_TRACK": "true",
    }


def ngrok_tunnels() -> List[Dict[str, Any]]:
    code, data = http_json("GET", f"{NGROK_API}/api/tunnels", timeout=3)
    return data.get("tunnels", []) if code == 200 and isinstance(data, dict) else []


def ngrok_urls() -> Dict[str, str]:
    out: Dict[str, str] = {}
    for t in ngrok_tunnels():
        url = t.get("public_url", "")
        if url.startswith("https://"):
            name = t.get("name", "")
            key = "computer" if "computer" in name else "openwebui"
            out.setdefault(key, url)
    return out


def ngrok_cmd() -> List[str]:
    b = ngrok_bin()
    if EXPOSE_COMPUTER and ENABLE_COMPUTER:
        cfg = RUN / "ngrok.yml"
        cfg.write_text(f"version: 3\nagent:\n  authtoken: {NGROK_TOKEN}\nendpoints:\n"
                       f"  - name: openwebui\n    upstream:\n      url: http://{WEBUI_HOST}:{WEBUI_PORT}\n"
                       f"  - name: computer\n    upstream:\n      url: http://{COMPUTER_HOST}:{COMPUTER_PORT}\n")
        os.chmod(cfg, 0o600)
        return [b, "start", "--all", "--config", str(cfg), "--log", "stdout"]
    cmd = [b, "http", f"{WEBUI_HOST}:{WEBUI_PORT}", "--log", "stdout"]
    if NGROK_DOMAIN:
        cmd += ["--url", f"https://{NGROK_DOMAIN}"]
    return cmd


def service_specs() -> List[Dict[str, Any]]:
    specs: List[Dict[str, Any]] = [{
        "name": "api", "cmd": [sys.executable, str(self_path()), "--serve-api"], "env": {}, "grace": 90,
        "health": lambda: http_ok(api_url("/health"), 4)}]
    if (VENV / "bin" / "open-webui").exists():
        specs.append({"name": "openwebui", "env": webui_env(), "grace": 1200, "after": ["api"],
                      "cmd": [str(VENV / "bin" / "open-webui"), "serve", "--host", WEBUI_HOST, "--port", str(WEBUI_PORT)],
                      "health": lambda: http_ok(webui_url("/health"), 5)})
    if ENABLE_COMPUTER and (VENV / "bin" / "cptr").exists():
        specs.append({"name": "computer", "env": {}, "grace": 180,
                      "cmd": [str(VENV / "bin" / "cptr"), "run", "--host", COMPUTER_HOST, "--port", str(COMPUTER_PORT), "--headless"],
                      "health": lambda: port_open(COMPUTER_HOST, COMPUTER_PORT)})
    if (RUN / "tunnel.enabled").exists() and NGROK_TOKEN:
        specs.append({"name": "ngrok", "env": {"NGROK_AUTHTOKEN": NGROK_TOKEN}, "grace": 45, "after": ["openwebui"],
                      "cmd": ngrok_cmd(), "health": lambda: bool(ngrok_tunnels())})
    return specs


def _write_public(urls: Dict[str, str]) -> None:
    if not urls:
        return
    text = urls.get("openwebui", "") + "\n"
    (RUN / "public_url.txt").write_text(text)
    if PERSIST:
        with contextlib.suppress(Exception):
            PERSIST.mkdir(parents=True, exist_ok=True)
            (PERSIST / "public_url.txt").write_text(text + (f"computer: {urls['computer']}\n" if "computer" in urls else ""))


def supervise() -> None:
    me, other = os.getpid(), _read_pid("supervisor")
    if other and other != me and _pid_alive(other) and _is_ours(other):
        log.info("supervisor already running (pid %s); exiting", other)
        return
    _pidfile("supervisor").write_text(str(me))
    stop = threading.Event()
    for s in (signal.SIGTERM, signal.SIGINT):
        signal.signal(s, lambda *_: stop.set())
    st: Dict[str, Dict[str, float]] = {}
    last_sync = time.time()
    last_urls: Dict[str, str] = {}
    log.info("Supervisor online (pid %d). Services are detached and survive this process.", me)
    while not stop.is_set():
        healthy: Dict[str, bool] = {}
        for sp in service_specs():
            name, now = sp["name"], time.time()
            s = st.setdefault(name, {"started": 0.0, "fails": 0, "restarts": 0, "next": 0.0, "ok_since": 0.0})
            try:
                h = bool(sp["health"]())
            except Exception:
                h = False
            healthy[name] = h
            if h:
                s["ok_since"] = s["ok_since"] or now
                if now - s["ok_since"] > 120:
                    s["fails"] = 0
                continue
            s["ok_since"] = 0.0
            if any(not healthy.get(d) for d in sp.get("after", [])):
                continue  # dependency not up yet
            alive = process_running(name)
            if alive and not s["started"]:
                s["started"] = now  # adopted process: grant grace before judging it
                continue
            if alive and now - s["started"] < sp["grace"]:
                continue
            if now < s["next"]:
                continue
            log.warning("[%s] %s -> (re)starting (restart #%d)", name, "unhealthy" if alive else "down", int(s["restarts"]) + 1)
            try:
                spawn(name, sp["cmd"], cwd=ROOT, env=sp.get("env"))
            except Exception:
                log.exception("[%s] spawn failed", name)
            s["started"], s["restarts"], s["fails"] = now, s["restarts"] + 1, s["fails"] + 1
            s["next"] = now + min(300.0, 5.0 * 2 ** min(int(s["fails"]), 6))
        urls = ngrok_urls() if "ngrok" in healthy else {}
        if urls != last_urls:
            _write_public(urls)
            last_urls = urls
        with contextlib.suppress(Exception):
            (RUN / "status.json").write_text(json.dumps({
                "time": time.time(), "public_urls": urls,
                "services": {n: {"healthy": h, "restarts": int(st[n]["restarts"])} for n, h in healthy.items()}}, indent=2))
        if PERSIST and time.time() - last_sync > 300:
            last_sync = time.time()
            try:
                log.info("Drive sync: %d files", sync_state())
            except Exception:
                log.exception("Drive sync failed")
        stop.wait(10)
    with contextlib.suppress(Exception):
        sync_state()
    log.info("Supervisor stopped (services keep running; use --stop to stop them)")


def ensure_supervisor() -> None:
    pid = _read_pid("supervisor")
    if pid and _pid_alive(pid) and _is_ours(pid):
        return
    spawn("supervisor", [sys.executable, str(self_path()), "--supervise"], cwd=ROOT)
    time.sleep(2)


# ---------------------------------------------------------------------
# BOOTSTRAP STEPS
# ---------------------------------------------------------------------


def preflight(args: argparse.Namespace) -> None:
    info(f"Colab: {IS_COLAB} | root: {is_root()} | sudo: {bool(shutil.which('sudo'))} | pkg mgr: {detect_pm()} | "
         f"python {sys.version_info[0]}.{sys.version_info[1]} | arch {platform.machine()}")
    g = gpu_info()
    info(f"GPU: {g['name'] or 'none (CPU mode)'}")
    if not shutil.which("curl") and not detect_pm():
        raise RuntimeError("curl is missing and no package manager is available")
    if sys.version_info < (3, 9):
        raise RuntimeError("Python 3.9+ required")
    if PERSIST:
        PERSIST.mkdir(parents=True, exist_ok=True)
        ok(f"Google Drive persistence: {PERSIST}")
    else:
        warn("NO Google Drive persistence: mount Drive in the notebook first "
             "(from google.colab import drive; drive.mount('/content/drive')). Continuing without it.")
        if _flag("SOVEREIGN_REQUIRE_DRIVE", False):
            raise RuntimeError("SOVEREIGN_REQUIRE_DRIVE=1 but Drive is not mounted")
    if not args.no_tunnel and not NGROK_TOKEN:
        raise RuntimeError("NGROK_AUTHTOKEN is not set. ngrok is your only way in - set it (Colab Secrets -> os.environ) "
                           "or pass --no-tunnel.")
    src = Path(__file__).resolve()
    if src != SELF:
        shutil.copy2(src, SELF)  # run daemons from local disk so a Drive hiccup can't break restarts
    if PERSIST and PERSIST not in src.parents:
        with contextlib.suppress(Exception):
            shutil.copy2(src, PERSIST / "sovereign_hive_factory.py")
    api_key()


def setup_ngrok() -> None:
    b = ensure_ngrok()
    sh([b, "config", "add-authtoken", NGROK_TOKEN], quiet=True, check=False, capture=True)


def step(title: str, fn: Callable[[], Any], *, optional: bool = False, repair: Optional[Callable[[], None]] = None) -> Any:
    banner(title)
    attempts = 3 if FREE_MODE else 1
    for i in range(1, attempts + 1):
        try:
            r = fn()
            ok(title)
            return r
        except Exception as e:  # noqa: BLE001
            fail(f"{title}: {e}")
            if i < attempts:
                warn(f"self-heal: repair + retry {i}/{attempts - 1}")
                if repair:
                    with contextlib.suppress(Exception):
                        repair()
                time.sleep(5 * i)
                continue
            if optional:
                warn(f"optional step skipped: {title}")
                return None
            raise


def wait_for(label: str, fn: Callable[[], bool], timeout: float, service: str = "", required: bool = True) -> bool:
    say(f"[…] waiting for {label} (up to {int(timeout)}s)")
    end, last = time.time() + timeout, 0.0
    while time.time() < end:
        if fn():
            ok(label)
            return True
        if time.time() - last > 30:
            last = time.time()
            say(f"    still waiting: {label} ({int(end - time.time())}s left)")
        time.sleep(3)
    msg = f"{label} did not come up.\n--- {service}.log tail ---\n{tail_log(service)}" if service else f"{label} timed out"
    if required:
        raise RuntimeError(msg)
    warn(msg)
    return False


def start_stack() -> None:
    ensure_supervisor()
    wait_for("Sovereign gateway", lambda: http_ok(api_url("/health")), 120, "api")

    def llama_up() -> bool:
        c, d = http_json("GET", api_url("/health"), timeout=5)
        return bool(c == 200 and d.get("llama", {}).get("up"))

    wait_for("llama-server (model loaded)", llama_up, STARTUP_TIMEOUT + 240, "llama")
    wait_for("Open WebUI (first start can take several minutes)", lambda: http_ok(webui_url("/health")), 1500, "openwebui")
    if ENABLE_COMPUTER and (VENV / "bin" / "cptr").exists():
        wait_for("Open WebUI Computer", lambda: port_open(COMPUTER_HOST, COMPUTER_PORT), 240, "computer", required=False)


def bootstrap_admin() -> Optional[Tuple[str, str]]:
    email = _env("SOVEREIGN_ADMIN_EMAIL", default="admin@sovereign.local")
    pw = _env("SOVEREIGN_ADMIN_PASSWORD") or secrets.token_urlsafe(12)
    code, body = http_json("POST", webui_url("/api/v1/auths/signup"),
                           {"name": "Admin", "email": email, "password": pw, "profile_image_url": "/user.png"})
    if code == 200:
        f = ROOT / "admin_credentials.txt"
        f.write_text(f"email: {email}\npassword: {pw}\n")
        with contextlib.suppress(OSError):
            os.chmod(f, 0o600)
        return email, pw
    info(f"Admin already exists or sign-up closed (HTTP {code}); not creating one.")
    return None


def smoke(args: argparse.Namespace) -> None:
    def chat(stream: bool, max_tokens: int) -> Any:
        body = {"model": MODEL_IDS["reasoning"], "messages": [{"role": "user", "content": "Say OK"}],
                "temperature": 0, "max_tokens": max_tokens, "stream": stream}
        if not stream:
            c, d = http_json("POST", api_url("/v1/chat/completions"), body, api_headers(), timeout=REQUEST_TIMEOUT)
            if c != 200:
                raise RuntimeError(f"HTTP {c}: {d}")
            m = d["choices"][0]["message"]
            return (m.get("content") or "").strip() or (m.get("reasoning_content") or "").strip()
        req = urllib.request.Request(api_url("/v1/chat/completions"), data=json.dumps(body).encode(), method="POST",
                                     headers={"Content-Type": "application/json", **api_headers()})
        got = b""
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
            while True:
                b = r.read(4096)
                if not b:
                    break
                got += b
        return b"data:" in got

    def rag_roundtrip() -> bool:
        http_json("POST", api_url("/v1/rag/documents"), {"title": "smoke", "content": "sovereign zebra quokka smoketest"}, api_headers())
        c, d = http_json("GET", api_url("/v1/rag/search?q=quokka"), headers=api_headers())
        return c == 200 and bool(d.get("results"))

    checks: List[Tuple[str, Callable[[], Any]]] = [
        ("gateway health", lambda: http_ok(api_url("/health"))),
        ("auth enforced (no key -> 401)", lambda: http_get(api_url("/v1/models"))[0] == 401),
        ("model list", lambda: len(http_json("GET", api_url("/v1/models"), headers=api_headers())[1].get("data", [])) == 3),
        ("1200-agent hive", lambda: http_json("GET", api_url("/hive/status"), headers=api_headers())[1].get("total") == TOTAL_AGENTS),
        ("RAG round-trip", rag_roundtrip),
        ("inference #1 (non-stream)", lambda: chat(False, 256)),
        ("inference #2 (lock released?)", lambda: chat(False, 64)),
        ("inference #3 (SSE stream)", lambda: chat(True, 64)),
        ("Open WebUI", lambda: http_ok(webui_url("/health"))),
        ("llama.cpp binary", llama_works),
    ]
    bad = []
    for name, fn in checks:
        try:
            good = bool(fn())
        except Exception as e:  # noqa: BLE001
            good = False
            warn(f"{name}: {e}")
        (ok if good else fail)(name)
        if not good:
            bad.append(name)
    if bad:
        raise RuntimeError(f"Smoke tests failed: {bad}")


def open_tunnel() -> Dict[str, str]:
    (RUN / "tunnel.enabled").write_text("1")
    ensure_supervisor()
    urls: Dict[str, str] = {}
    end = time.time() + 120
    while time.time() < end and "openwebui" not in urls:
        urls = ngrok_urls()
        time.sleep(2)
    if "openwebui" not in urls:
        raise RuntimeError(f"ngrok gave no public URL.\n{tail_log('ngrok')}")
    _write_public(urls)
    good = wait_for("public URL reachable through ngrok", lambda: http_ok(urls["openwebui"] + "/health", 8,
                    {"ngrok-skip-browser-warning": "1"}), 90, required=False)
    if not good:
        warn("URL exists but the health probe failed; try opening it in your browser.")
    return urls


def watch_line() -> str:
    try:
        st = json.loads((RUN / "status.json").read_text())
        svc = " ".join(f"{n}{'✓' if v['healthy'] else '✗'}" for n, v in st["services"].items())
        url = st.get("public_urls", {}).get("openwebui", "-")
        return f"{time.strftime('%H:%M:%S')} {svc} {url}"
    except Exception:
        return f"{time.strftime('%H:%M:%S')} (status pending)"


def bootstrap(args: argparse.Namespace) -> None:
    banner("SOVEREIGN HIVE FACTORY v4")
    step("0/11 Preflight", lambda: preflight(args))
    step("1/11 System packages", lambda: sys_install(["git", "curl", "cmake", "compiler", "pkgconf"]))
    sys_install(["ffmpeg"], required=False)
    step("2/11 Restore chats + hive memory from Drive", restore_state, optional=True)
    if not args.no_tunnel:
        step("3/11 ngrok agent", setup_ngrok)
    step("4/11 Python 3.11 env + Open WebUI", ensure_python_env,
         repair=lambda: (shutil.rmtree(VENV, ignore_errors=True), shutil.rmtree(PYDIR, ignore_errors=True)))
    step("5/11 llama.cpp", ensure_llama, repair=lambda: shutil.rmtree(LLAMA_SRC / "build", ignore_errors=True))
    step("6/11 Models (Drive master copy -> local disk)", ensure_models)

    def node_cline() -> None:
        c = ensure_cline()
        ok(f"Cline: {c}")

    step("7/11 Node 20+ and Cline CLI", node_cline, optional=True)
    step("8/11 Start supervisor + services", start_stack)
    creds = step("9/11 Open WebUI admin account", bootstrap_admin, optional=True)
    c = cline_path()
    if c:
        say("[•] Cline -> local gateway: " + ("configured" if configure_cline(c) else "auto-config failed (run: cline auth)"))
    step("10/11 Smoke tests (gate before going public)", lambda: smoke(args))

    urls: Dict[str, str] = {}
    if args.no_tunnel:
        warn("--no-tunnel: nothing is public.")
    else:
        urls = step("11/11 Public tunnel (Open WebUI only)", lambda: open_tunnel()) or {}
    if PERSIST:
        with contextlib.suppress(Exception):
            info(f"Drive snapshot: {sync_state()} files")

    banner("SOVEREIGN HIVE ONLINE")
    if urls.get("openwebui"):
        say(f"  PUBLIC URL : {urls['openwebui']}")
        say(f"  (also saved to Drive: {PERSIST / 'public_url.txt' if PERSIST else RUN / 'public_url.txt'})")
    if urls.get("computer"):
        say(f"  COMPUTER   : {urls['computer']}   <-- full shell access, protect it!")
    if creds:
        say(f"\n  Open WebUI admin  ->  {creds[0]} / {creds[1]}   (change it after first login)")
    say("\n  Next: Open WebUI -> Admin Panel -> Settings -> General: turn OFF 'Enable New Sign Ups'.")
    say("  Services are DETACHED: closing the tab / locking the phone / interrupting this cell does not stop them.")
    say("  Recycled runtime? Re-run the same cell; everything restores from Drive.\n")
    if args.detach:
        return
    say("Watching (Ctrl-C / interrupt only stops this watcher, not the services):")
    try:
        while True:
            say(watch_line())
            time.sleep(60)
    except KeyboardInterrupt:
        say("\nWatcher stopped. Services keep running. Use --status / --url / --stop.")


# ---------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------


def cmd_status() -> None:
    banner("SOVEREIGN STATUS")
    for name, host, port in (("Gateway", API_HOST, API_PORT), ("llama.cpp", LLAMA_HOST, LLAMA_PORT),
                             ("Open WebUI", WEBUI_HOST, WEBUI_PORT), ("Computer", COMPUTER_HOST, COMPUTER_PORT)):
        say(f"{name:14} {host}:{port:<6} {'ONLINE' if port_open(host, port) else 'OFFLINE'}")
    say(f"Supervisor     {'RUNNING' if process_running('supervisor') else 'STOPPED'}")
    say(f"Drive          {PERSIST or 'not mounted'}")
    say(f"Public URL     {ngrok_urls().get('openwebui') or '(tunnel down)'}")
    c, d = http_json("GET", api_url("/health"), timeout=5)
    if c == 200:
        say(f"Model          {d['llama']}\nHive           {d['hive']}")


def main() -> None:
    global FREE_MODE
    ap = argparse.ArgumentParser(description="Sovereign Hive Factory v4")
    ap.add_argument("--bootstrap", action="store_true", help="install/restore everything, start services, open tunnel")
    ap.add_argument("--run-free", action="store_true", help="unattended: auto repair + retry failed steps")
    ap.add_argument("--no-tunnel", action="store_true", help="do not start ngrok")
    ap.add_argument("--detach", action="store_true", help="return after bootstrap instead of watching")
    ap.add_argument("--serve-api", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--supervise", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--url", action="store_true", help="print the current public URL")
    ap.add_argument("--stop", action="store_true", help="stop all services")
    ap.add_argument("--sync", action="store_true", help="snapshot chats/hive memory to Drive now")
    ap.add_argument("--smoke-test", action="store_true")
    args = ap.parse_args()
    FREE_MODE = args.run_free or _flag("SOVEREIGN_RUN_FREE", False)
    mode = "api" if args.serve_api else "supervisor" if args.supervise else "bootstrap"
    prepare_dirs()
    setup_logging(mode)
    if args.serve_api:
        return serve_api()
    if args.supervise:
        return supervise()
    if args.stop:
        with contextlib.suppress(Exception):
            sync_state()
        stop_all()
        say("All Sovereign services stopped.")
        return
    if args.status:
        return cmd_status()
    if args.url:
        saved = (RUN / "public_url.txt").read_text().strip() if (RUN / "public_url.txt").exists() else ""
        say(ngrok_urls().get("openwebui") or saved or "no public URL")
        return
    if args.sync:
        say(f"synced {sync_state()} files to {PERSIST}")
        return
    if args.smoke_test:
        return smoke(args)
    if not args.bootstrap:
        say("Use:  python sovereign_hive_factory.py --bootstrap --run-free")
        return
    try:
        bootstrap(args)
    except KeyboardInterrupt:
        say("\nInterrupted. Any started services keep running (--stop to stop them).")
    except Exception as e:  # noqa: BLE001
        fail(str(e))
        say("Services already started were left running. Logs: " + str(LOGS))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
