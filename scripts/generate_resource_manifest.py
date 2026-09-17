# -*- coding: utf-8 -*-
"""resource_manifest.json 自动生成器（PR 合并后由 CI 运行）。

职责（见实施计划 §5-§8）：
1. 从 .resourceignore 生成 required_dirs / required_files；
2. 从 version 生成 resource_version；
3. 从 .resourceignore 的包含/排除规则和实际资源文件生成 file_hashes；
4. 默认完整重建 manifest，不依赖旧 manifest 内容；
5. `--incremental` 仅供 CI 优化：用旧 manifest 作为 hash 缓存，按 Git diff 更新，
   但输出必须与完整重建字节一致；
6. 稳定序列化（字典序、2 空格、ensure_ascii=False、结尾换行）。

约束：
- manifest 没有人工维护字段：所有内容必须能从其他事实源完整重建；
- format_version 是生成器输出 schema 版本；当前固定为 2；
- required_dirs / required_files 与 file_hashes 范围都只从 .resourceignore 读取；
- 禁止跟随符号链接；禁止无依据的限制或兜底——错误显式暴露。
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from hash_rules import HashRuleSet

MANIFEST_PATH = "resource_manifest.json"
RULES_PATH = ".resourceignore"
VERSION_PATH = "version"
FORMAT_VERSION = 2


class ManifestGenError(Exception):
    """生成器操作失败（显式暴露，不做静默兜底）。"""


# ---------- git / fs 基础设施 ----------


def git_output(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(
        ["git", *args], capture_output=True, text=True, cwd=cwd, check=False
    )
    if result.returncode != 0:
        raise ManifestGenError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def find_checkpoint(cwd: Path | None = None) -> str:
    """manifest 最后一次被修改的提交。

    依赖前提：新规则禁止人工修改 manifest，该提交之后的变化都应被追平。
    """
    out = git_output("log", "-1", "--format=%H", "--", MANIFEST_PATH, cwd=cwd).strip()
    if not out:
        raise ManifestGenError(
            f"no commit ever touched {MANIFEST_PATH}; cannot determine checkpoint"
        )
    return out


def diff_name_status(base: str, head: str, cwd: Path | None = None) -> list[tuple[str, str, str]]:
    """返回 [(status, path, new_path|'')]；R 状态附带新路径。"""
    out = git_output(
        "diff", "--name-status", "--find-renames",
        base, head, cwd=cwd,
    )
    changes: list[tuple[str, str, str]] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status = parts[0]
        if status.startswith("R"):
            changes.append((status, parts[1], parts[2]))
        else:
            changes.append((status, parts[-1], ""))
    return changes


def read_version(root: Path) -> str:
    raw = (root / VERSION_PATH).read_text(encoding="utf-8")
    value = raw.strip()
    if not value.isdigit() or int(value) <= 0 or value.startswith("0"):
        raise ManifestGenError(f"invalid {VERSION_PATH}: {value!r}")
    return value


# ---------- 哈希计算 ----------


def sha256_file(path: Path) -> str:
    """流式计算 SHA-256；不跟随符号链接。"""
    if path.is_symlink():
        raise ManifestGenError(f"symlink not allowed: {path}")
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_repo_file(root: Path, rel_path: str) -> str:
    return sha256_file(root / rel_path)


def managed_hash_paths(root: Path, rules: HashRuleSet) -> list[str]:
    """按 .resourceignore 枚举当前需要进入 file_hashes 的文件。"""

    current: set[str] = set()
    for directory in rules.scan_dirs():
        base = root / directory
        if base.is_dir():
            for path in base.rglob("*"):
                if path.is_file() or path.is_symlink():
                    relative = path.relative_to(root).as_posix()
                    if path.is_symlink():
                        raise ManifestGenError(f"symlink not allowed: {relative}")
                    if rules.matches(relative):
                        current.add(relative)
    for relative in rules.scan_files():
        path = root / relative
        if path.is_file() and rules.matches(relative):
            current.add(relative)
    return sorted(current)


def build_file_hashes(root: Path, rules: HashRuleSet) -> dict[str, str]:
    """完全由规则文件与当前资源内容生成 file_hashes。"""

    return {
        relative: hash_repo_file(root, relative)
        for relative in managed_hash_paths(root, rules)
    }


# ---------- 普通增量 ----------


def _is_rename(status: str) -> bool:
    return status.startswith("R")


def apply_changes(
    hashes: dict[str, str],
    rules,
    changes: list[tuple[str, str, str]],
    version: str,
    hash_fn=None,
    root: Path | None = None,
) -> None:
    """按 `git diff --name-status` 增量调整 hashes（原地修改）。

    若 changes 中包含规则文件（.resourceignore），委托 reconcile_scope 做
    受管范围对账；否则纯增量，不读取任何未变化文件。
    """
    if hash_fn is None:
        hash_fn = lambda p: hash_repo_file(root or Path("."), p)  # noqa: E731
    if root is None:
        root = Path(".")
    # 规则变化 → 走 reconciliation（它会额外处理普通变化）
    if any(path == RULES_PATH for _, path, _ in changes):
        reconcile_scope(hashes, rules, changes, root=root, hash_fn=hash_fn)
        return
    for status, old_path, new_path in changes:
        if _is_rename(status):
            # 旧 key 无论是否存在都尝试删除（可能此前未被管理）
            hashes.pop(old_path, None)
            if rules.matches(new_path):
                hashes[new_path] = hash_fn(new_path)
        elif status == "A":
            if rules.matches(old_path):
                hashes[old_path] = hash_fn(old_path)
        elif status == "M":
            if rules.matches(old_path):
                hashes[old_path] = hash_fn(old_path)
        elif status == "D":
            hashes.pop(old_path, None)
        else:
            # 未预期的 status（如 T 类型变化）：显式暴露，不静默跳过
            raise ManifestGenError(f"unexpected git status {status!r} for {old_path}")


# ---------- 规则变更 reconciliation ----------


def reconcile_scope(
    hashes: dict[str, str],
    rules,
    changes: list[tuple[str, str, str]],
    root: Path,
    hash_fn=None,
) -> None:
    """规则变更模式：对账受管范围（计划 §7）。

    只枚举正向 include 规则允许的目录/文件，不进行全仓库扫描：
    - 新进入范围的文件 → 计算 SHA；
    - 已退出范围 / 已删除的文件 → 删除 hash；
    - 本次 diff 中内容修改过的文件 → 重新 hash；
    - 其余已有 hash 的文件 → 直接复用旧值，不读文件内容。
    """
    if hash_fn is None:
        hash_fn = lambda p: hash_repo_file(root, p)  # noqa: E731

    # 本次内容变化集合（含 rename 的新路径），用于重新 hash
    changed: set[str] = set()
    for status, old_path, new_path in changes:
        if _is_rename(status):
            changed.add(old_path)
            if new_path:
                changed.add(new_path)
        elif status in ("A", "M"):
            changed.add(old_path)

    # 1) 枚举当前规则下的受管文件集合（只扫 include 目录与 include 单文件）
    current = set(managed_hash_paths(root, rules))

    # 2) 清理退出范围或已删除的 key
    for key in list(hashes):
        if key not in current:
            del hashes[key]

    # 3) 补齐新进入范围的文件；本次内容有变化的重新 hash
    for rel in sorted(current):
        if rel not in hashes or rel in changed:
            hashes[rel] = hash_fn(rel)


# ---------- manifest 生成与序列化 ----------


def set_resource_version(manifest: dict, version: str) -> None:
    if not version.isdigit() or int(version) <= 0 or version.startswith("0"):
        raise ValueError(f"resource_version must be positive integer, got {version!r}")
    manifest["resource_version"] = version


def serialize(manifest: dict) -> str:
    """稳定序列化：顶层固定规范序、file_hashes 字典序、2 空格缩进、
    ensure_ascii=False、结尾换行。相同内容必然字节一致。

    遇到未知顶层键显式失败：新增顶层字段属于资源契约迁移，
    必须同步修改生成器，不允许静默透传。
    """
    canonical_order = (
        "format_version",
        "required_dirs",
        "required_files",
        "resource_version",
        "file_hashes",
    )
    unknown = set(manifest) - set(canonical_order)
    if unknown:
        raise ManifestGenError(
            f"unknown manifest top-level keys {sorted(unknown)}; "
            "extend the generator's canonical order when migrating the contract"
        )
    ordered: dict = {}
    for key in canonical_order:
        if key not in manifest:
            if key == "required_files" and manifest.get("format_version") == 1:
                continue
            raise ManifestGenError(f"manifest missing required key {key!r}")
        value = manifest[key]
        ordered[key] = dict(sorted(value.items())) if key == "file_hashes" else value
    return json.dumps(ordered, ensure_ascii=False, indent=2) + "\n"


def generate(root: Path | None = None) -> str:
    """仅凭维护侧事实源与当前资源内容完整生成 manifest。"""
    if root is None:
        root = Path(".")
    version = read_version(root)
    rules_text = (root / RULES_PATH).read_text(encoding="utf-8")
    rules = HashRuleSet.parse(rules_text)
    manifest = {
        "format_version": FORMAT_VERSION,
        "required_dirs": rules.required_dirs(),
        "required_files": rules.required_files(),
    }

    manifest["file_hashes"] = build_file_hashes(root, rules)
    set_resource_version(manifest, version)
    return serialize(manifest)


def generate_incremental(root: Path | None = None) -> str:
    """基于已生成 manifest 增量更新；仅作为 CI 性能优化。"""

    if root is None:
        root = Path(".")
    version = read_version(root)
    rules_text = (root / RULES_PATH).read_text(encoding="utf-8")
    rules = HashRuleSet.parse(rules_text)
    manifest = {
        "format_version": FORMAT_VERSION,
        "required_dirs": rules.required_dirs(),
        "required_files": rules.required_files(),
    }
    current_manifest = json.loads((root / MANIFEST_PATH).read_text(encoding="utf-8"))

    checkpoint = find_checkpoint(cwd=root)
    changes = diff_name_status(checkpoint, "HEAD", cwd=root)
    hashes = dict(current_manifest.get("file_hashes", {}))
    apply_changes(hashes, rules, changes, version=version, root=root)

    manifest["file_hashes"] = hashes
    set_resource_version(manifest, version)
    return serialize(manifest)


def main() -> int:
    args = sys.argv[1:]
    incremental = False
    if args and args[0] == "--incremental":
        incremental = True
        args = args[1:]
    if len(args) > 1:
        print(
            "usage: generate_resource_manifest.py [--incremental] [root]",
            file=sys.stderr,
        )
        return 2
    root = Path(args[0]) if args else Path(".")
    try:
        generator = generate_incremental if incremental else generate
        (root / MANIFEST_PATH).write_text(generator(root), encoding="utf-8")
    except ManifestGenError as exc:
        print(f"manifest generation failed:\n{exc}", file=sys.stderr)
        return 1
    print("manifest generated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
