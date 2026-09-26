#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""codekit sealing —— 01-A13 不可变发布的参考实现（01 文档 4.2.8、8.3）。

流程：校验 → 在目标所在目录独占创建临时文件 → 完整写入、flush、fsync、关闭 → 重新打开读回并计算
SHA-256（必须等于调用方字节的摘要）→ 以不覆盖的方式发布（os.link 到最终名）→ POSIX 上 fsync 父目录
→ 构造 ResourceRef → 调用 index_commit(ref) → 返回 ResourceRef。

范围与前提（裁决 R-P9，01-D06）
- A13 的范围是“发布与索引补偿”：独占创建临时文件、读回核验、不覆盖已有文件、索引失败不返回引用、
  可用相同字节幂等补录。路径安全不在 A13 范围内。
- store_root 必须是可信核心独占控制的目录。sealing 不防御被攻击者控制（或可被其他主体写入）的存储根，
  也不防御其中预置的硬链接、链接或并发替换。
- 存储根内的路径步进（每一级 resolve、_check_link_hops 逐跳核对、真实名称核对）是静态审阅 + 纵深防御，
  不是安全访问保证：它只覆盖下列“已检测的情形”，已知不检测、不保证的情形见 SEALING_LIMITATIONS。

已检测的情形（逐项有测试，见 protocols-api.md 第 15 节）
- 某一级解析后的最终目标在根外（包括指向“只在 str.lower() 下与根同名”的兄弟目录的链接）→ E_PATH_ESCAPE；
- 同一分段内经根外链接绕回根内的链接链（含相对目标、Windows 上目标文本中按词法折叠的 ".."、名称末尾带点或
  空格的链接）→ E_PATH_ESCAPE；
- 目标写法不受支持或语义无法确定、未识别的名称代理类重解析点、逐跳展开终点与 resolve 结果不同 →
  E_PATH_RESOLUTION_FAILED（失败关闭）；
- 大小写别名 → E_PATH_COLLISION；手工设置的短名等其他未登记别名 → E_PATH_RESOLUTION_FAILED；
- 发布后复查发现最终路径解析到根外 → E_PATH_ESCAPE（只能事后报告，不删除已创建的链接）。

明确限制（01-D06，另见 SEALING_LIMITATIONS）
- 不提供崩溃持久性证明：没有做断电/崩溃注入测试；Windows 上不 fsync 目录（标准库无法打开目录句柄）。
- 不防同一账户下其他进程的篡改或并发替换：路径检查与使用之间仍有 TOCTOU 窗口。检查之后祖先目录或目标
  被替换时，下一级 mkdir 或发布可能落到根外；发布后的越界复查只能事后报告（E_PATH_ESCAPE），不删除已创建的
  链接。
- 硬链接不检测：存储根中已有、与根外文件共享数据的硬链接按普通文件读取，并按幂等接受相同字节；根外改写后
  只有读取时的摘要核验能发现。
- 挂载点、尚未枚举的 NT/Win32 名称写法、不带名称代理位的重解析点不在检测范围内；POSIX 未实测（NOT_RUN）。
- 不是生产级安全访问实现：没有按目录句柄逐级访问，也不拒绝根目录内部的链接（只要解析后仍在根内）。
- 发布依赖文件系统支持硬链接（os.link）；不支持时底层 OSError 原样抛出，不返回引用。
- 环境类 OSError（磁盘满、权限、被其他进程独占打开等）在 seal_bytes 与 read_sealed 中都原样抛出，
  异常消息可能含本机绝对路径，调用方不得原样外发。
- 发布之前失败（读回摘要不符、os.link 抛环境类 OSError 等）时，本次调用按需新建的**空**父目录会残留，
  不回滚：并发写入者可能正要在同一目录中写入，按 8.4 不在不确定时清理；目录中不会残留文件。

与 protocols 的绑定：seal_bytes/read_sealed 使用“传入的 registry 所属的那个 protocols 模块”做校验并
抛出它的 ProtocolError。因此无论调用方以包方式导入（codekit.protocols），还是像仓库测试那样按文件加载
而不登记到 sys.modules，捕获到的都是调用方自己那份 ProtocolError。registry 由调用方信任。

副作用：导入本模块只加载标准库模块（不加载 protocols.py，也不读写任何数据文件）、不启动进程、
不联网、不读环境变量；只有被调用时才访问调用方传入的存储根目录（必须由可信核心独占控制，见上）。
"""
from __future__ import annotations

import hashlib
import hmac
import importlib.util
import os
import secrets
import stat
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

#: POSIX 上发布后 fsync 父目录；Windows 跳过（标准库无法打开目录句柄做 fsync）。
DIRECTORY_FSYNC_SUPPORTED = os.name != "nt"
#: 已知不检测、不保证的情形与环境限制（01-D06；P4 第 5 轮按裁决 R-P9 补充）。已检测的情形见模块说明与
#: protocols-api.md 第 15 节。
SEALING_LIMITATIONS = (
    "不提供崩溃持久性证明（未做断电/崩溃注入测试）",
    "Windows 上不 fsync 父目录",
    "不防同一账户下其他进程的篡改或并发替换（存在 TOCTOU 窗口）",
    "不是生产级安全文件访问实现（01-D06）",
    "发布依赖文件系统支持硬链接（os.link）",
    "发布之前失败时可能残留本次新建的空父目录（不回滚，8.4）",
    "store_root 必须是可信核心独占控制的目录：sealing 不防御被攻击者控制（或可被其他主体写入）的存储根，"
    "也不防御其中预置的硬链接、链接或并发替换；存储根内的链接与别名核对只是纵深防御（R-P9）",
    "A13 的范围是发布与索引补偿（独占创建、读回核验、不覆盖、索引失败不返回引用、可幂等补录），不含路径安全（R-P9）",
    "检查之后父目录或目标被替换时，已完成的检查不再成立：下一级 mkdir 或发布可能落到根外，发布后复查只能事后报告",
    "硬链接不检测：存储根中与根外文件共享数据的硬链接按普通文件读取、按幂等接受相同字节，根外改写只能在读取时由"
    "摘要核验发现",
    "挂载点不保证：卷挂载点形式（卷 GUID 目标）的链接按不受支持的写法失败关闭；POSIX 的 bind mount 等挂载不是链接，不检测",
    "NT 层与 Win32 层名称语义差异只覆盖已枚举的写法；尚未枚举的写法不保证被识别，不带名称代理位的重解析点按普通名称处理",
    "POSIX 平台（Linux/macOS）未实测（NOT_RUN）",
)
_TEMP_PREFIX = ".codekit-seal-"
_TEMP_SUFFIX = ".tmp"
_READ_CHUNK = 1 << 20
_PROTOCOL_NAMES = ("ProtocolError", "ResourceKindRegistry", "validate_business_path",
                   "validate_resource_ref", "_check_listed_name", "_is_within", "_check_link_hops")


def _protocols_for(registry: Any) -> SimpleNamespace:
    """取得定义 registry 类型的 protocols 模块中的校验函数与 ProtocolError。"""
    for klass in type(registry).__mro__:
        method = klass.__dict__.get("is_file_kind")
        if klass.__name__ != "ResourceKindRegistry" or method is None:
            continue
        namespace = getattr(method, "__globals__", None)
        if (isinstance(namespace, dict) and namespace.get("ResourceKindRegistry") is klass
                and all(name in namespace for name in _PROTOCOL_NAMES)):
            return SimpleNamespace(**{name: namespace[name] for name in _PROTOCOL_NAMES})
    raise TypeError("registry must be a protocols.ResourceKindRegistry")


def _load_protocols() -> ModuleType:
    """供模块属性 sealing.ProtocolError 使用：包内相对导入；否则复用 sys.modules 中按同一文件加载的
    protocols；都没有时才按文件加载一份。seal_bytes/read_sealed 不依赖它。"""
    if __package__:
        from . import protocols as package_protocols  # type: ignore[no-redef]
        return package_protocols
    sibling = os.path.join(os.path.dirname(os.path.abspath(__file__)), "protocols.py")
    wanted = os.path.normcase(os.path.abspath(sibling))
    for module in list(sys.modules.values()):
        module_file = getattr(module, "__file__", None)
        if module_file and os.path.normcase(os.path.abspath(module_file)) == wanted:
            return module
    name = "_codekit_protocols_for_sealing"
    spec = importlib.util.spec_from_file_location(name, sibling)
    if spec is None or spec.loader is None:
        raise ImportError("cannot locate protocols.py next to sealing.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def __getattr__(name: str) -> Any:
    if name == "ProtocolError":
        return _load_protocols().ProtocolError
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _trusted_root(p: SimpleNamespace, store_root: Any, phase: str) -> Path:
    if not isinstance(store_root, (str, os.PathLike)):
        raise TypeError("store_root must be a path")
    try:
        root = Path(store_root).resolve(strict=True)
        is_dir = root.is_dir()
    except (OSError, RuntimeError):
        raise p.ProtocolError("E_PATH_ROOT", phase=phase, reason="store_root_unresolvable") from None
    if not is_dir:
        raise p.ProtocolError("E_PATH_ROOT", phase=phase, reason="store_root_not_directory")
    return root


def _resolve_within(p: SimpleNamespace, root: Path, path: Path, *, missing_code: str,
                    phase: str) -> Path:
    try:
        resolved = path.resolve(strict=True)
    except (FileNotFoundError, NotADirectoryError):
        raise p.ProtocolError(missing_code, field="/path", phase=phase,
                              reason="target_not_found") from None
    except (OSError, RuntimeError):
        raise p.ProtocolError("E_PATH_RESOLUTION_FAILED", field="/path", phase=phase,
                              reason="static_resolution_failed") from None
    if not p._is_within(root, resolved):  # 与 protocols 共用：按组件逐字比较，不按 str.lower()
        raise p.ProtocolError("E_PATH_ESCAPE", field="/path", phase=phase,
                              reason="resolved_outside_store_root")
    return resolved


def _step(p: SimpleNamespace, root: Path, current: Path, segment: str, *, missing_code: str,
          phase: str) -> Path:
    """解析 current/segment 并核对这一级（静态审阅 + 纵深防御，不是安全访问保证，裁决 R-P9）。已检测的情形：
    - 最终目标不在根内 → E_PATH_ESCAPE（resolved_outside_store_root）；
    - protocols._check_link_hops 逐跳展开时遇到位于根外的链接对象 → E_PATH_ESCAPE（link_hop_outside_trusted_root，
      P4 第 3 轮）；Windows 上目标文本中的 "." 与 ".." 按词法折叠、名称按逐字路径访问（P4 第 4 轮）；目标写法不受
      支持或语义无法确定、未识别的名称代理类重解析点、展开终点与 resolve 结果不同 → E_PATH_RESOLUTION_FAILED；
    - segment 不是 current 中登记的真实名称：大小写别名 E_PATH_COLLISION，手工设置的短名等其他别名
      E_PATH_RESOLUTION_FAILED。
    悬空链接按 missing_code 报告。已知不检测的情形（检查后的替换、硬链接等）见 SEALING_LIMITATIONS。"""
    resolved = _resolve_within(p, root, current / segment, missing_code=missing_code, phase=phase)
    p._check_link_hops(root, current, segment, field="/path", phase=phase, resolved=resolved)
    p._check_listed_name(current, segment, field="/path", phase=phase)
    return resolved


def _ensure_parent(p: SimpleNamespace, root: Path, business_path: str) -> Path:
    """逐级确认（必要时创建）父目录：每一级先按 _step 解析并核对，再在其下创建下一级。

    已检测的情形（静态审阅 + 纵深防御，裁决 R-P9）：
    - 已存在的链接/junction 不会被 mkdir 穿透（FileExistsError），随后 _step 按上面的规则核对：最终目标在根外，
      或逐跳展开时遇到位于根外的链接对象 → E_PATH_ESCAPE，这一级之下不再 mkdir、不发布文件；
    - “位于根内”按 resolve 后路径组件逐字比较（protocols._is_within），不按 str.lower()：名称只在 lower() 下与根的
      祖先相同的根外兄弟目录（例如含 U+212A 开尔文符号，或位于大小写敏感的 NTFS 目录中）算越界；
    - 悬空的链接祖先 → E_PATH_RESOLUTION_FAILED；已存在的祖先分段是普通文件 → E_PATH_RESOLUTION_FAILED
      （reason=ancestor_not_directory）。
    mkdir 只在这一次核对通过的目录下执行。已知不检测：核对之后祖先被换成指向根外的链接（TOCTOU、并发替换）
    时，下一级 mkdir 会落到根外（复审已用注入实测，01-D06）；存储根本身必须由可信核心独占控制（见
    SEALING_LIMITATIONS）。这里新建的目录在随后的步骤失败时不删除（只会是空目录，见模块说明）。
    """
    current = root
    for segment in business_path.split("/")[:-1]:
        try:
            os.mkdir(current / segment)
        except FileExistsError:
            pass
        resolved = _step(p, root, current, segment, missing_code="E_PATH_RESOLUTION_FAILED",
                         phase="seal")
        if not resolved.is_dir():
            raise p.ProtocolError("E_PATH_RESOLUTION_FAILED", field="/path", phase="seal",
                                  reason="ancestor_not_directory")
        current = resolved
    return current


def _require_regular_file(p: SimpleNamespace, path: Path) -> None:
    """最终名已被占用时，占用者必须是普通文件；目录（含指向根内目录的 junction）等 → E_RESOURCE_CONFLICT。"""
    try:
        mode = os.stat(path).st_mode
    except FileNotFoundError:
        raise p.ProtocolError("E_PATH_RESOLUTION_FAILED", field="/path", phase="seal",
                              reason="target_not_found") from None
    if not stat.S_ISREG(mode):
        raise p.ProtocolError("E_RESOURCE_CONFLICT", field="/path", phase="seal",
                              reason="immutable_path_occupied_by_non_file")


def _read_all(p: SimpleNamespace, path: Path, phase: str) -> bytes:
    """读一次完整字节；只接受普通文件（POSIX 上用 O_NONBLOCK 打开，避免被 FIFO 阻塞）。"""
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(path, flags)
    except FileNotFoundError:
        raise p.ProtocolError("E_RESOURCE_MISSING", field="/path", phase=phase,
                              reason="resource_not_found") from None
    except (IsADirectoryError, PermissionError):
        if path.is_dir():
            raise p.ProtocolError("E_RESOURCE_MISSING", field="/path", phase=phase,
                                  reason="not_regular_file") from None
        raise
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise p.ProtocolError("E_RESOURCE_MISSING", field="/path", phase=phase,
                                  reason="not_regular_file")
        chunks = []
        while True:
            chunk = os.read(fd, _READ_CHUNK)
            if not chunk:
                break
            chunks.append(chunk)
    finally:
        os.close(fd)
    return b"".join(chunks)


def _remove_quietly(path: Path) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass  # 残留临时文件以 .codekit-seal- 前缀可识别；不在不确定时递归清理（8.4）


def _write_temp(directory: Path, raw: bytes) -> Path:
    for _ in range(16):
        candidate = directory / (_TEMP_PREFIX + secrets.token_hex(16) + _TEMP_SUFFIX)
        try:
            fd = os.open(candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0),
                         0o600)
        except FileExistsError:
            continue
        try:
            try:
                view = memoryview(raw)
                written = 0
                while written < len(raw):
                    written += os.write(fd, view[written:])
                os.fsync(fd)
            finally:
                os.close(fd)
        except BaseException:
            _remove_quietly(candidate)
            raise
        return candidate
    raise FileExistsError("could not create a unique temporary file for sealing")


def _fsync_directory(directory: Path) -> None:
    fd = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _digest_equal(raw: bytes, expected: str) -> bool:
    return hmac.compare_digest(hashlib.sha256(raw).hexdigest(), expected)


def seal_bytes(store_root: Path, business_path: str, raw: bytes, *, kind: str, resource_id: str,
               registry: Any, index_commit: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    """把 raw 封存为 store_root/<business_path> 的不可变版本，并返回其 ResourceRef（只含 kind/id/sha256/path）。

    - store_root 必须是可信核心独占控制的目录（裁决 R-P9）：sealing 不防御被攻击者控制的存储根，也不防御其中
      预置的硬链接、链接或并发替换。A13 的范围是发布与索引补偿，不含路径安全（见 SEALING_LIMITATIONS）。
    - business_path 按 validate_business_path 校验；kind 必须是已登记的文件型类型；父目录不存在时在根内逐级创建。
    - 读回的字节摘要与 sha256(raw) 不符 → 删除临时文件，E_RESOURCE_HASH_MISMATCH。
    - 最终名已存在：字节相同 → 幂等（删除临时文件，照常提交索引并返回引用）；不同 → E_RESOURCE_CONFLICT，不覆盖；
      最终名被目录等非普通文件占用 → E_RESOURCE_CONFLICT（reason=immutable_path_occupied_by_non_file）。
    - 路径核对是静态审阅 + 纵深防御（R-P9），已检测的情形：每一级（包括已存在的最终名）解析后的最终目标在
      store_root 之外 → E_PATH_ESCAPE（按 resolve 后路径组件逐字比较，见 protocols._is_within）；逐跳展开时遇到
      位于根外的链接对象 → E_PATH_ESCAPE（protocols._check_link_hops）；目标写法不受支持、未识别的名称代理类
      重解析点、展开终点不一致、悬空链接 → E_PATH_RESOLUTION_FAILED；拼写不是磁盘上登记的真实名称：大小写别名
      E_PATH_COLLISION，其他未登记的别名（例如手工设置、不含 "~" 的短名）E_PATH_RESOLUTION_FAILED（否则返回的
      path 拼写在磁盘上并不存在）。已知不检测的情形（硬链接、检查后的替换等）见 SEALING_LIMITATIONS。
    - index_commit(ref) 抛异常 → 不返回引用；文件留作“未引用候选”，抛 E_RESOURCE_INDEX_FAILED
      （retryable=True；用相同字节再次调用 seal_bytes 是幂等的，可据此补录）。
    - POSIX 上发布后 fsync 父目录；Windows 跳过（DIRECTORY_FSYNC_SUPPORTED=False）。
    - 环境类 OSError（磁盘满、权限、文件系统不支持硬链接）原样抛出，不返回引用。
    - index_commit 不可调用 → 写入任何东西之前抛 TypeError。index_commit 收到的是引用的副本，它修改参数
      不影响返回值。
    - 发布之前失败时不残留文件，但本次新建的空父目录不回滚（见模块说明）。
    - 8.3 短名形态的业务路径（例如 CODEKI~1.TMP，正是临时文件自动获得的短名）在词法层即以
      E_PATH_RESERVED 拒绝（裁决 R-P3），不会让 os.link 命中临时文件自己的短名。
    """
    p = _protocols_for(registry)
    p.validate_business_path(business_path)
    if type(raw) is not bytes:
        raise p.ProtocolError("E_RESOURCE_BYTES", phase="seal", reason="bytes_input_required")
    if not callable(index_commit):
        raise TypeError("index_commit must be callable")
    expected = hashlib.sha256(raw).hexdigest()
    ref = {"kind": kind, "id": resource_id, "sha256": expected, "path": business_path}
    p.validate_resource_ref(ref, registry)
    if not registry.is_file_kind(kind):
        raise p.ProtocolError("E_RESOURCE_KIND", field="/kind", phase="seal",
                              reason="file_resource_kind_required")
    root = _trusted_root(p, store_root, "seal")
    parent = _ensure_parent(p, root, business_path)
    final_name = business_path.split("/")[-1]
    final = parent / final_name
    if os.path.lexists(final):  # 已存在的最终名（包括链接）必须解析到根内、拼写一致、是普通文件
        existing = _step(p, root, parent, final_name, missing_code="E_PATH_RESOLUTION_FAILED",
                         phase="seal")
        _require_regular_file(p, existing)
    temp = _write_temp(parent, raw)
    try:
        written = _read_all(p, temp, "seal")
        if len(written) != len(raw) or not _digest_equal(written, expected):
            raise p.ProtocolError("E_RESOURCE_HASH_MISMATCH", field="/sha256", phase="seal",
                                  reason="written_bytes_digest_mismatch")
        try:
            os.link(temp, final)
        except FileExistsError:
            existing_path = _step(p, root, parent, final_name,
                                  missing_code="E_PATH_RESOLUTION_FAILED", phase="seal")
            _require_regular_file(p, existing_path)
            if not _digest_equal(_read_all(p, existing_path, "seal"), expected):
                raise p.ProtocolError("E_RESOURCE_CONFLICT", field="/path", phase="seal",
                                      reason="immutable_path_has_different_content") from None
    finally:
        _remove_quietly(temp)
    # 发布后复查：只能事后报告越界，已创建的链接不删除（无法确认它仍是本次创建的对象，01-D06）。
    _resolve_within(p, root, final, missing_code="E_RESOURCE_MISSING", phase="seal")
    if DIRECTORY_FSYNC_SUPPORTED:
        _fsync_directory(parent)
    try:
        index_commit(dict(ref))
    except Exception:  # noqa: BLE001 —— 任何索引失败都不能让调用方拿到“已发布”的引用
        raise p.ProtocolError("E_RESOURCE_INDEX_FAILED", phase="index",
                              reason="index_commit_failed_unreferenced_candidate_kept") from None
    return dict(ref)


def read_sealed(store_root: Path, ref: dict[str, Any], registry: Any) -> bytes:
    """按 ResourceRef 读取已封存资源：只读一次字节，核验完整 SHA-256 后返回这同一份字节。

    store_root 的前提与 seal_bytes 相同：必须由可信核心独占控制（裁决 R-P9）。
    不存在（含悬空链接、中间段是文件）或不是普通文件 E_RESOURCE_MISSING；摘要不符 E_RESOURCE_HASH_MISMATCH。
    逐级核对与 seal_bytes 共用 _step（静态审阅 + 纵深防御），已检测的情形：某一级解析后的最终目标在 store_root
    之外，或逐跳展开时遇到位于根外的链接对象（经根外绕回根内）→ E_PATH_ESCAPE（按 resolve 后路径组件逐字比较，
    见 protocols._is_within 与 _check_link_hops）；目标写法不受支持、未识别的名称代理类重解析点、展开终点不一致
    → E_PATH_RESOLUTION_FAILED；拼写不是磁盘上登记的真实名称（大小写别名 E_PATH_COLLISION，手工设置的短名等
    其他别名 E_PATH_RESOLUTION_FAILED；自动生成的 8.3 短名形态在校验 ref 时已按 E_PATH_RESERVED 拒绝）。已知不
    检测、不保证的情形见 SEALING_LIMITATIONS：检查之后的并发替换（TOCTOU）、与根外文件共享数据的硬链接（读到的
    是根外文件的字节，只要摘要相符就返回）、挂载点、尚未枚举的 NT/Win32 写法、POSIX 未实测（01-D06）。
    环境类 OSError（例如文件被其他进程独占打开时的 PermissionError）原样抛出，消息可能含本机路径，调用方不得原样外发。
    调用方应消费返回的字节，而不是之后再按路径重新读取（4.2.8）。
    """
    p = _protocols_for(registry)
    p.validate_resource_ref(ref, registry)
    if not registry.is_file_kind(ref["kind"]):
        raise p.ProtocolError("E_RESOURCE_KIND", field="/kind", phase="read",
                              reason="file_resource_kind_required")
    root = _trusted_root(p, store_root, "read")
    resolved = root
    for segment in ref["path"].split("/"):
        resolved = _step(p, root, resolved, segment, missing_code="E_RESOURCE_MISSING", phase="read")
    data = _read_all(p, resolved, "read")
    if not _digest_equal(data, ref["sha256"]):
        raise p.ProtocolError("E_RESOURCE_HASH_MISMATCH", field="/sha256", phase="read",
                              reason="stored_bytes_digest_mismatch")
    return data


__all__ = ["seal_bytes", "read_sealed", "DIRECTORY_FSYNC_SUPPORTED", "SEALING_LIMITATIONS"]
