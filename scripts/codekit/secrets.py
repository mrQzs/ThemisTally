"""凭据库：环境变量 → 操作系统凭据库 → 0600 文件；只报有无与来源，不报值（2.7.0）。

决策模型的 key 这类凭据以**环境变量名**为名字（例如 ``TYPESAFE_API_KEY``）。解析顺序与 hermes-jev-skills 的
keystore 相同：进程环境变量 → 系统凭据库（Windows 凭据管理器、macOS Keychain、Linux ``secret-tool``）→
``~/.config/code-kit/secrets/<名字>``（0600；Windows 上用 ``icacls`` 只留当前用户）。

进程级开关 ``CODEKIT_SECRET_STORE``：``system``（缺省）、``file``（跳过系统凭据库，只用文件）、``off``（只认环境变量，
测试用）。``XDG_CONFIG_HOME`` 决定文件目录。

本模块不打印、不记录值；``describe`` 只返回名字与来源。写入走原子替换；Windows 凭据管理器用 ``ctypes`` 调
``advapi32``（``CredReadW`` / ``CredWriteW`` / ``CredDeleteW``，``CRED_TYPE_GENERIC``，``TargetName`` 为
``code-kit:<名字>``）。后端的可用性在调用时判断，导入无副作用。
"""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional

TARGET_PREFIX = "code-kit:"
STORE_ENV = "CODEKIT_SECRET_STORE"
STORE_MODES = ("system", "file", "off")
SOURCES = ("env", "credential_store", "file", "none")
KEYCHAIN_SERVICE = "Code-Kit"
_SECURITY = "/usr/bin/security"
MAX_SECRET_CHARS = 4096


class SecretError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__("%s: %s" % (code, detail) if detail else code)
        self.code = code
        self.detail = detail


def _check_name(name: Any) -> str:
    if not isinstance(name, str) or not name or len(name) > 128 or not all(
            ch.isalnum() or ch == "_" for ch in name) or name[0].isdigit():
        raise SecretError("name", "a secret is named by an environment variable name")
    return name


def looks_like_secret(value: Any) -> bool:
    """粘贴错误的廉价检查：非空、无空白、可打印、不超过上限。"""
    return (isinstance(value, str) and 8 <= len(value.strip()) <= MAX_SECRET_CHARS
            and not any(ch.isspace() for ch in value.strip()) and value.strip().isprintable())


def store_mode(environ: Optional[Mapping[str, str]] = None) -> str:
    environ = os.environ if environ is None else environ
    mode = (environ.get(STORE_ENV) or "system").strip().lower()
    return mode if mode in STORE_MODES else "system"


def secrets_dir(environ: Optional[Mapping[str, str]] = None) -> Path:
    environ = os.environ if environ is None else environ
    base = environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "code-kit" / "secrets"


# ---------------------------------------------------------------------------
# 系统凭据库后端
# ---------------------------------------------------------------------------

class WindowsCredentialManager:
    """Windows 凭据管理器（advapi32）。``api`` 可注入，测试用假对象。"""

    name = "windows-credential-manager"
    CRED_TYPE_GENERIC = 1
    CRED_PERSIST_LOCAL_MACHINE = 2
    ERROR_NOT_FOUND = 1168

    def __init__(self, api: Any = None) -> None:
        self._api = api

    def available(self) -> bool:
        return os.name == "nt" or self._api is not None

    def _advapi(self) -> Any:
        if self._api is not None:
            return self._api
        import ctypes
        return ctypes.WinDLL("advapi32", use_last_error=True)

    def _target(self, name: str) -> str:
        return TARGET_PREFIX + name

    def read(self, name: str) -> Optional[str]:
        import ctypes
        from ctypes import wintypes
        api = self._advapi()
        pointer = ctypes.c_void_p()
        ok = api.CredReadW(ctypes.c_wchar_p(self._target(name)), wintypes.DWORD(self.CRED_TYPE_GENERIC),
                           wintypes.DWORD(0), ctypes.byref(pointer))
        if not ok:
            return None
        try:
            cred = ctypes.cast(pointer, ctypes.POINTER(_credential_struct())).contents
            size = int(cred.CredentialBlobSize)
            if not size:
                return ""
            raw = ctypes.string_at(cred.CredentialBlob, size)
            return raw.decode("utf-16-le")
        finally:
            api.CredFree(pointer)

    def write(self, name: str, value: str) -> None:
        import ctypes
        from ctypes import wintypes
        api = self._advapi()
        blob = value.encode("utf-16-le")
        buffer = ctypes.create_string_buffer(blob, len(blob))
        cred = _credential_struct()()
        cred.Flags = 0
        cred.Type = self.CRED_TYPE_GENERIC
        cred.TargetName = self._target(name)
        cred.Comment = "Code-Kit secret (%s)" % name
        cred.CredentialBlobSize = len(blob)
        cred.CredentialBlob = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char))
        cred.Persist = self.CRED_PERSIST_LOCAL_MACHINE
        cred.AttributeCount = 0
        cred.Attributes = None
        cred.TargetAlias = None
        cred.UserName = name
        if not api.CredWriteW(ctypes.byref(cred), wintypes.DWORD(0)):
            raise SecretError("credential_store", "CredWriteW failed (error %s)" % ctypes.get_last_error())

    def delete(self, name: str) -> bool:
        import ctypes
        from ctypes import wintypes
        api = self._advapi()
        return bool(api.CredDeleteW(ctypes.c_wchar_p(self._target(name)), wintypes.DWORD(self.CRED_TYPE_GENERIC),
                                    wintypes.DWORD(0)))


_CREDENTIAL_STRUCT: Any = None


def _credential_struct() -> Any:
    """CREDENTIALW 的 ctypes 结构（只定义一次）。"""
    global _CREDENTIAL_STRUCT
    if _CREDENTIAL_STRUCT is None:
        import ctypes
        from ctypes import wintypes

        class FILETIME(ctypes.Structure):
            _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]

        class CREDENTIALW(ctypes.Structure):
            _fields_ = [("Flags", wintypes.DWORD), ("Type", wintypes.DWORD), ("TargetName", ctypes.c_wchar_p),
                        ("Comment", ctypes.c_wchar_p), ("LastWritten", FILETIME),
                        ("CredentialBlobSize", wintypes.DWORD), ("CredentialBlob", ctypes.POINTER(ctypes.c_char)),
                        ("Persist", wintypes.DWORD), ("AttributeCount", wintypes.DWORD),
                        ("Attributes", ctypes.c_void_p), ("TargetAlias", ctypes.c_wchar_p),
                        ("UserName", ctypes.c_wchar_p)]
        _CREDENTIAL_STRUCT = CREDENTIALW
    return _CREDENTIAL_STRUCT


class CommandStore:
    """macOS Keychain（``security``）或 Linux ``secret-tool``：通过子进程，值只经 stdin 或参数传给它们。"""

    def __init__(self, kind: str, runner: Optional[Callable[..., Any]] = None) -> None:
        self.kind = kind
        self.name = {"keychain": "macos-keychain", "secret-tool": "secret-tool"}[kind]
        self._run = runner or (lambda *a, **k: subprocess.run(*a, **k))

    def available(self) -> bool:
        if self.kind == "keychain":
            return sys.platform == "darwin" and os.path.exists(_SECURITY)
        return shutil.which("secret-tool") is not None

    def read(self, name: str) -> Optional[str]:
        if self.kind == "keychain":
            cmd = [_SECURITY, "find-generic-password", "-w", "-s", KEYCHAIN_SERVICE, "-a", name]
        else:
            cmd = ["secret-tool", "lookup", "service", KEYCHAIN_SERVICE, "account", name]
        proc = self._run(cmd, capture_output=True, text=True, timeout=10, check=False)
        if proc.returncode != 0 or not proc.stdout.strip():
            return None
        return proc.stdout.strip()

    def write(self, name: str, value: str) -> None:
        if self.kind == "keychain":
            cmd = [_SECURITY, "add-generic-password", "-U", "-s", KEYCHAIN_SERVICE, "-a", name, "-w", value]
            proc = self._run(cmd, capture_output=True, text=True, timeout=10, check=False)
        else:
            cmd = ["secret-tool", "store", "--label", "Code-Kit %s" % name, "service", KEYCHAIN_SERVICE, "account", name]
            proc = self._run(cmd, input=value, capture_output=True, text=True, timeout=10, check=False)
        if proc.returncode != 0:
            raise SecretError("credential_store", "%s exited %s" % (cmd[0], proc.returncode))

    def delete(self, name: str) -> bool:
        if self.kind == "keychain":
            cmd = [_SECURITY, "delete-generic-password", "-s", KEYCHAIN_SERVICE, "-a", name]
        else:
            cmd = ["secret-tool", "clear", "service", KEYCHAIN_SERVICE, "account", name]
        proc = self._run(cmd, capture_output=True, text=True, timeout=10, check=False)
        return proc.returncode == 0


class FileStore:
    """``<secrets_dir>/<名字>``：0600 创建、原子替换；Windows 上用 icacls 只留当前用户（尽力而为）。"""

    name = "file"

    def __init__(self, directory: Optional[Path] = None, environ: Optional[Mapping[str, str]] = None) -> None:
        self.directory = Path(directory) if directory else secrets_dir(environ)

    def available(self) -> bool:
        return True

    def path(self, name: str) -> Path:
        return self.directory / name

    def read(self, name: str) -> Optional[str]:
        path = self.path(name)
        try:
            if path.is_symlink() or not path.is_file():
                return None
            return path.read_text(encoding="utf-8").strip() or None
        except OSError:
            return None

    def write(self, name: str, value: str) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.directory, stat.S_IRWXU)
        except OSError:
            pass
        path = self.path(name)
        temp = path.with_name(path.name + ".tmp")
        fd = os.open(str(temp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(value + "\n")
        except BaseException:
            try:
                os.unlink(str(temp))
            except OSError:
                pass
            raise
        try:
            os.chmod(temp, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass
        os.replace(str(temp), str(path))
        if os.name == "nt":
            _restrict_windows_acl(path)

    def delete(self, name: str) -> bool:
        path = self.path(name)
        try:
            os.unlink(str(path))
        except FileNotFoundError:
            return False
        return True


def _restrict_windows_acl(path: Path) -> None:
    """只留当前用户的完全控制：失败不抛（文件已经在用户目录下）。"""
    user = os.environ.get("USERNAME")
    if not user or not shutil.which("icacls"):
        return
    try:
        subprocess.run(["icacls", str(path), "/inheritance:r", "/grant:r", "%s:F" % user],
                       capture_output=True, timeout=20, check=False)
    except (OSError, subprocess.SubprocessError):
        pass


# ---------------------------------------------------------------------------
# 解析
# ---------------------------------------------------------------------------

def system_backend() -> Optional[Any]:
    """本机可用的系统凭据库，没有则 None。"""
    candidates: List[Any] = [WindowsCredentialManager(), CommandStore("keychain"), CommandStore("secret-tool")]
    for backend in candidates:
        try:
            if backend.available():
                return backend
        except OSError:
            continue
    return None


def backends(environ: Optional[Mapping[str, str]] = None) -> List[Any]:
    """按解析顺序（环境变量之后）的后端列表；``CODEKIT_SECRET_STORE`` 为 off 时为空。"""
    mode = store_mode(environ)
    if mode == "off":
        return []
    found: List[Any] = []
    if mode == "system":
        system = system_backend()
        if system is not None:
            found.append(system)
    found.append(FileStore(environ=environ))
    return found


def source(name: str, environ: Optional[Mapping[str, str]] = None) -> str:
    """凭据在哪一层：env / credential_store / file / none。不返回值。"""
    name = _check_name(name)
    environ = os.environ if environ is None else environ
    if environ.get(name):
        return "env"
    for backend in backends(environ):
        try:
            value = backend.read(name)
        except (OSError, SecretError):
            value = None
        if value:
            return "file" if isinstance(backend, FileStore) else "credential_store"
    return "none"


def resolve(name: str, environ: Optional[Mapping[str, str]] = None) -> Optional[str]:
    """值本身：只给要用它构造请求头的调用方。环境变量优先。"""
    name = _check_name(name)
    environ = os.environ if environ is None else environ
    value = environ.get(name)
    if value:
        return value
    for backend in backends(environ):
        try:
            value = backend.read(name)
        except (OSError, SecretError):
            value = None
        if value:
            return value
    return None


def store(name: str, value: str, environ: Optional[Mapping[str, str]] = None) -> str:
    """存进第一个可用后端（系统凭据库优先），返回后端名。值不合形状时拒绝。"""
    name = _check_name(name)
    if not looks_like_secret(value):
        raise SecretError("shape", "the value does not look like a credential (8-%d printable characters, no spaces)"
                          % MAX_SECRET_CHARS)
    chosen = backends(environ)
    if not chosen:
        raise SecretError("store_off", "%s=off: nothing is stored" % STORE_ENV)
    backend = chosen[0]
    backend.write(name, value.strip())
    return backend.name


def remove(name: str, environ: Optional[Mapping[str, str]] = None) -> List[str]:
    """从每个后端删除；返回删掉了的后端名。"""
    name = _check_name(name)
    removed: List[str] = []
    for backend in backends(environ):
        try:
            if backend.delete(name):
                removed.append(backend.name)
        except (OSError, SecretError):
            continue
    return removed


def describe(name: str, environ: Optional[Mapping[str, str]] = None) -> Dict[str, Any]:
    mode = store_mode(environ)
    system = system_backend() if mode == "system" else None
    return {"name": name, "source": source(name, environ), "store_mode": mode,
            "system_backend": system.name if system is not None else None,
            "file_dir": str(secrets_dir(environ))}
