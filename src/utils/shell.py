"""
Shell execution utilities with idempotency, logging and clean environment.
"""
import subprocess
import os
import sys
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict


@dataclass
class CmdResult:
    returncode: int
    stdout: str
    stderr: str
    cmd: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# PyInstaller cleanup (prevents LD_LIBRARY_PATH pollution)
_PYINSTALLER_VARS = {"LD_LIBRARY_PATH", "LD_PRELOAD", "_MEIPASS2", "PYTHONPATH", "PYTHONHOME"}


def clean_env() -> Dict[str, str]:
    return {k: v for k, v in os.environ.items() if k not in _PYINSTALLER_VARS}


def run(cmd: str, check: bool = False, timeout: int = 300, capture: bool = True,
        cwd: Optional[str] = None, env: Optional[Dict[str, str]] = None) -> CmdResult:
    """Execute shell command with proper error handling."""
    merged_env = clean_env()
    if env:
        merged_env.update(env)

    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=capture, text=True,
            timeout=timeout, cwd=cwd, env=merged_env
        )
    except subprocess.TimeoutExpired:
        return CmdResult(returncode=124, stdout="", stderr="timeout", cmd=cmd)
    except Exception as e:
        return CmdResult(returncode=1, stdout="", stderr=str(e), cmd=cmd)

    r = CmdResult(
        returncode=result.returncode,
        stdout=result.stdout or "",
        stderr=result.stderr or "",
        cmd=cmd
    )

    if check and not r.ok:
        print(f"  ERROR executing: {cmd}")
        if r.stderr:
            print(f"  {r.stderr[:500]}")
        raise RuntimeError(f"Command failed: {cmd}")

    return r


def run_remote(ip: str, cred: Dict[str, str], cmd: str, timeout: int = 300, check: bool = False) -> CmdResult:
    """Execute command on remote server via SSH."""
    import shlex
    escaped = cmd.replace("'", "'\''")

    if cred.get("type") == "password":
        pw = shlex.quote(cred["value"])
        ssh = f"sshpass -p {pw} ssh"
        user = cred.get("user", "root")
    elif cred.get("type") == "key":
        ssh = f"ssh -i '{cred['value']}'"
        user = cred.get("user", "root")
    else:
        raise ValueError("cred must have type='password' or type='key'")

    full = f"{ssh} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {user}@{ip} '{escaped}'"
    return run(full, check=check, timeout=timeout)


def write_file(path: str, content: str, mode: int = 0o644) -> None:
    """Atomic file write (write to temp then rename)."""
    tmp = f"{path}.tmp"
    with open(tmp, "w") as f:
        f.write(content)
    os.chmod(tmp, mode)
    os.replace(tmp, path)


def read_file(path: str, default: str = "") -> str:
    try:
        with open(path) as f:
            return f.read()
    except FileNotFoundError:
        return default


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def is_installed(binary: str) -> bool:
    return run(f"which {binary}", check=False, timeout=5).ok


def get_public_ip() -> str:
    for url in ["ifconfig.me", "icanhazip.com", "api.ipify.org"]:
        r = run(f"curl -s4 --max-time 5 {url}", check=False, timeout=10)
        ip = r.stdout.strip()
        if ip and all(c in "0123456789." for c in ip) and len(ip) <= 15:
            return ip
    r = run("hostname -I 2>/dev/null | awk '{print $1}'", check=False)
    return r.stdout.strip()


def wait_for_port(port: int, host: str = "127.0.0.1", timeout: int = 60) -> bool:
    import socket
    deadline = __import__('time').time() + timeout
    while __import__('time').time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2):
                return True
        except:
            __import__('time').sleep(1)
    return False
