#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PR 阶段资源版本与显式资源策略检查。

安全模型：workflow 使用 ``pull_request_target`` 检出 base，并执行 base 上的本脚本与
规则解析器；PR 只提供待解析的 ``.resourceignore`` 文本与 Git tree，不执行 PR 代码。
"""
import argparse
import json
import re
import subprocess
import sys

from hash_rules import HashRuleError, HashRuleSet, RULES_PATH

PATTERN = re.compile(r"^[1-9][0-9]*$")


class VersionCheckError(Exception):
    pass


def read_file(ref: str, path: str, cwd: str | None = None) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "show", f"{ref}:{path}"], text=True, stderr=subprocess.DEVNULL, cwd=cwd
        )
    except subprocess.CalledProcessError:
        return None


def tracked_files(ref: str, cwd: str | None = None) -> list[str]:
    out = subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", ref],
        text=True, stderr=subprocess.DEVNULL, cwd=cwd,
    )
    return [line for line in out.splitlines() if line]


def changed_entries(
    base_ref: str,
    head_ref: str,
    cwd: str | None = None,
) -> list[tuple[str, str, str]]:
    out = subprocess.check_output(
        ["git", "diff", "--name-status", "--find-renames", base_ref, head_ref],
        text=True,
        stderr=subprocess.DEVNULL,
        cwd=cwd,
    )
    entries: list[tuple[str, str, str]] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status = parts[0]
        if status.startswith("R"):
            if len(parts) != 3:
                raise VersionCheckError(f"invalid rename diff entry: {line!r}")
            entries.append((status, parts[1], parts[2]))
        else:
            if len(parts) != 2:
                raise VersionCheckError(f"invalid diff entry: {line!r}")
            entries.append((status, parts[1], ""))
    return entries


def parse_version(raw: str) -> int:
    value = raw[:-1] if raw.endswith("\n") else raw
    if not PATTERN.fullmatch(value):
        raise VersionCheckError(f'invalid version: "{value}"\nexpected positive decimal integer')
    return int(value)


def load_rules(ref: str, cwd: str | None = None) -> HashRuleSet:
    raw = read_file(ref, RULES_PATH, cwd=cwd)
    if raw is None:
        raise VersionCheckError(f"{ref}/{RULES_PATH} is missing")
    try:
        return HashRuleSet.parse(raw)
    except HashRuleError as exc:
        raise VersionCheckError(f"{ref}/{RULES_PATH} has invalid rules: {exc}") from exc


def _entry_paths(entry: tuple[str, str, str]) -> tuple[str, ...]:
    _, old_path, new_path = entry
    return (old_path, new_path) if new_path else (old_path,)


def _is_included_change(
    entry: tuple[str, str, str],
    *,
    base_rules: HashRuleSet,
    head_rules: HashRuleSet,
    version_file: str,
    manifest_file: str,
) -> bool:
    status, old_path, new_path = entry

    def is_control(path: str) -> bool:
        return path in {RULES_PATH, version_file, manifest_file}

    if status.startswith("R"):
        return (
            not is_control(old_path) and base_rules.classify(old_path) is True
        ) or (
            not is_control(new_path) and head_rules.classify(new_path) is True
        )
    if status == "D":
        return not is_control(old_path) and base_rules.classify(old_path) is True
    if status in {"A", "M", "T"}:
        return not is_control(old_path) and head_rules.classify(old_path) is True
    raise VersionCheckError(f"unexpected git status {status!r} for {old_path}")


def check(
    base_ref: str,
    head_ref: str,
    *,
    version_file: str,
    manifest_file: str,
    cwd: str | None = None,
    allow_manifest_edit: bool = False,
) -> None:
    entries = changed_entries(base_ref, head_ref, cwd=cwd)
    changed_paths = {
        path
        for entry in entries
        for path in _entry_paths(entry)
        if path
    }

    if manifest_file in changed_paths and not allow_manifest_edit:
        raise VersionCheckError(
            f"{manifest_file} is generated automatically after merge; "
            "do not edit it in pull requests"
        )

    if allow_manifest_edit and entries and all(
        set(_entry_paths(entry)) <= {manifest_file} for entry in entries
    ):
        print("Resource Version Check: skipped (generated manifest sync PR)")
        return

    base_rules = load_rules(base_ref, cwd=cwd)
    head_rules = load_rules(head_ref, cwd=cwd)

    undeclared = [
        path
        for path in tracked_files(head_ref, cwd=cwd)
        if path != RULES_PATH and not head_rules.is_declared(path)
    ]
    if undeclared:
        raise VersionCheckError(
            "undeclared tracked paths:\n"
            + "\n".join(f"- {path}" for path in undeclared)
        )

    manifest_raw = read_file(head_ref, manifest_file, cwd=cwd)
    if manifest_raw is None:
        raise VersionCheckError(f"head/{manifest_file} is missing")
    try:
        json.loads(manifest_raw)
    except json.JSONDecodeError as exc:
        raise VersionCheckError(f"invalid {manifest_file}: {exc.msg}") from exc

    base_raw = read_file(base_ref, version_file, cwd=cwd)
    head_raw = read_file(head_ref, version_file, cwd=cwd)
    if head_raw is None:
        raise VersionCheckError(f"head/{version_file} is missing")
    head_version = parse_version(head_raw)
    base_version = parse_version(base_raw) if base_raw is not None else None

    resource_changes = any(
        _is_included_change(
            entry,
            base_rules=base_rules,
            head_rules=head_rules,
            version_file=version_file,
            manifest_file=manifest_file,
        )
        for entry in entries
    )
    version_changed = version_file in changed_paths

    if base_version is None:
        if head_version != 1:
            raise VersionCheckError(
                f"initial migration must use version 1, got {head_version}"
            )
    elif (version_changed or resource_changes) and head_version <= base_version:
        raise VersionCheckError(
            f"head version {head_version} must be greater than base version {base_version}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--version-file", required=True)
    parser.add_argument("--manifest-file", required=True)
    parser.add_argument("--cwd", default=None, help="git 命令工作目录（测试用；生产默认当前目录）")
    parser.add_argument("--allow-manifest-edit", action="store_true",
                        help="仅由 Resource Manifest Sync 对 bot 生成的 manifest PR 使用")
    args = parser.parse_args()
    try:
        check(
            args.base,
            args.head,
            version_file=args.version_file,
            manifest_file=args.manifest_file,
            cwd=args.cwd,
            allow_manifest_edit=args.allow_manifest_edit,
        )
    except VersionCheckError as exc:
        print(f"resource version check failed:\n{exc}", file=sys.stderr)
        return 1
    print("Resource Version Check: passed")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
