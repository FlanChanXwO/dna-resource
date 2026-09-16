# -*- coding: utf-8 -*-
"""resource_manifest.json 自动生成器（PR 合并后由 CI 运行）。

职责（见实施计划 §5-§8）：
1. 读取 version 与现有 resource_manifest.json；
2. 读取 .resourcehashes；
3. 用 `git log -1 -- resource_manifest.json` 找 checkpoint；
4. 处理 `checkpoint..HEAD` 的文件变化；
5. 普通增量：只处理 diff 文件，不做目录扫描；
6. 规则变更（.resourcehashes 在 diff 中）：额外做受管范围 reconciliation，
   只枚举规则允许的范围，未变化的文件复用旧 hash；
7. 设置 resource_version = version；
8. 稳定序列化（字典序、2 空格、ensure_ascii=False、结尾换行）。

约束：
- 只允许修改 manifest 的 resource_version 与 file_hashes；
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
RULES_PATH = ".resourcehashes"
VERSION_PATH = "version"

# manifest 的契约字段：生成器绝不触碰
PRESERVED_KEYS = ("format_version", "required_dirs")


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

    若 changes 中包含规则文件（.resourcehashes），委托 reconcile_scope 做
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
    current: set[str] = set()
    for d in rules.scan_dirs():
        base = root / d
        if base.is_dir():
            for p in base.rglob("*"):
                if p.is_file() or p.is_symlink():
                    rel = p.relative_to(root).as_posix()
                    if p.is_symlink():
                        raise ManifestGenError(f"symlink not allowed: {rel}")
                    if rules.matches(rel):
                        current.add(rel)
    for f in rules.scan_files():
        if (root / f).is_file() and rules.matches(f):
            current.add(f)

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
    canonical_order = ("format_version", "required_dirs", "resource_version", "file_hashes")
    unknown = set(manifest) - set(canonical_order)
    if unknown:
        raise ManifestGenError(
            f"unknown manifest top-level keys {sorted(unknown)}; "
            "extend the generator's canonical order when migrating the contract"
        )
    ordered: dict = {}
    for key in canonical_order:
        if key not in manifest:
            raise ManifestGenError(f"manifest missing required key {key!r}")
        value = manifest[key]
        ordered[key] = dict(sorted(value.items())) if key == "file_hashes" else value
    return json.dumps(ordered, ensure_ascii=False, indent=2) + "\n"


def generate(root: Path | None = None) -> str:
    """主入口：返回序列化后的 manifest 文本。"""
    if root is None:
        root = Path(".")
    version = read_version(root)
    manifest = json.loads((root / MANIFEST_PATH).read_text(encoding="utf-8"))
    rules_text = (root / RULES_PATH).read_text(encoding="utf-8")
    rules = HashRuleSet.parse(rules_text)

    checkpoint = find_checkpoint(cwd=root)
    changes = diff_name_status(checkpoint, "HEAD", cwd=root)
    hashes = dict(manifest.get("file_hashes", {}))
    apply_changes(hashes, rules, changes, version=version, root=root)

    manifest["file_hashes"] = hashes
    set_resource_version(manifest, version)
    return serialize(manifest)


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    try:
        (root / MANIFEST_PATH).write_text(generate(root), encoding="utf-8")
    except ManifestGenError as exc:
        print(f"manifest generation failed:\n{exc}", file=sys.stderr)
        return 1
    print("manifest generated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
