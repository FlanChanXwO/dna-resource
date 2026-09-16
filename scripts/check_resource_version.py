#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PR 阶段资源版本检查（资源 manifest 改为合并后自动生成后的新规则）。

职责（计划 §9）：
- 纯维护文件变化（docs/ scripts/ .github/ README/AGENTS/CHANGELOG）：跳过；
- 资源发生变化：head version 必须 > base version（正整数规则不变）；
- `.resourcehashes` 变化：视为资源契约变化，必须 bump version，
  并用 base 分支（本文件所在检出）的 parser 校验规则语法；
- PR 修改 resource_manifest.json：直接失败——合并后由 bot 自动生成；
- 不再校验 PR 内 resource_version == version（那是合并后 sync 的职责）。

安全模型（计划 §10）：本脚本始终从 base 检出运行，不执行 PR 中的代码。
"""
import argparse
import json
import re
import subprocess
import sys

PATTERN = re.compile(r"^[1-9][0-9]*$")

# 与资源无关的前缀路径：只改动这些内容时跳过版本检查（按前缀匹配）。
# scripts/tests/ 是维护工具自身的测试目录，位于 scripts/ 前缀下，天然豁免
UNRELATED_PREFIXES = ("docs/", "scripts/", ".github/")
# 与资源无关的仓库级文件（精确匹配）
UNRELATED_FILES = {"AGENTS.md", "README.md", "CHANGELOG.md"}

MANIFEST = "resource_manifest.json"
HASH_RULES = ".resourcehashes"


class VersionCheckError(Exception):
    pass


def read_file(ref: str, path: str, cwd: str | None = None) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "show", f"{ref}:{path}"], text=True, stderr=subprocess.DEVNULL, cwd=cwd
        )
    except subprocess.CalledProcessError:
        return None


def changed_files(base_ref: str, head_ref: str, cwd: str | None = None) -> list[str]:
    out = subprocess.check_output(
        ["git", "diff", "--name-only", base_ref, head_ref],
        text=True, stderr=subprocess.DEVNULL, cwd=cwd,
    )
    return [line for line in out.splitlines() if line]


def is_unrelated(path: str) -> bool:
    return path in UNRELATED_FILES or path.startswith(UNRELATED_PREFIXES)


def has_resource_changes(files: list[str]) -> bool:
    # 默认视为资源相关（包括 version、resource_manifest.json 与全部资源目录），
    # 只有明确列出的资源无关内容才豁免，避免新增目录被误判为免检
    return any(not is_unrelated(f) for f in files)


def parse_version(raw: str) -> int:
    value = raw[:-1] if raw.endswith("\n") else raw
    if not PATTERN.fullmatch(value):
        raise VersionCheckError(f'invalid version: "{value}"\nexpected positive decimal integer')
    return int(value)


def validate_rules_text(text: str, source: str) -> None:
    """用 base 检出中的规则 parser 校验 .resourcehashes 语法（fail fast）。"""
    # 延迟导入：parser 与本脚本同目录（base 检出），不属于资源无关运行的额外依赖
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
    from hash_rules import HashRuleError, HashRuleSet

    try:
        HashRuleSet.parse(text)
    except HashRuleError as exc:
        raise VersionCheckError(f"{source} has invalid rules: {exc}") from exc


def check(base_ref: str, head_ref: str, cwd: str | None = None) -> None:
    files = changed_files(base_ref, head_ref, cwd=cwd)

    # manifest 是合并后自动生成的产物：PR 内出现即失败
    if MANIFEST in files:
        raise VersionCheckError(
            f"{MANIFEST} is generated automatically after merge; "
            "do not edit it in pull requests"
        )

    rules_changed = HASH_RULES in files
    if not has_resource_changes(files):
        if rules_changed:
            # .resourcehashes 属于资源契约，即使路径以资源无关前缀开头也不豁免
            # （当前它就在仓库根目录，实际不会命中；这里显式防御语义）
            pass
        else:
            print("Resource Version Check: skipped (no resource-related changes)")
            return

    base_raw, head_raw = read_file(base_ref, "version", cwd=cwd), read_file(head_ref, "version", cwd=cwd)
    if head_raw is None:
        raise VersionCheckError("head/version is missing")
    head = parse_version(head_raw)
    if base_raw is None:
        if head != 1:
            raise VersionCheckError(f"initial migration must use version 1, got {head}")
    elif head <= parse_version(base_raw):
        raise VersionCheckError(f"head version {head} must be greater than base version {parse_version(base_raw)}")

    # manifest 仍必须存在且是合法 JSON（插件要能消费），但 resource_version 不再在此校验
    manifest_raw = read_file(head_ref, MANIFEST, cwd=cwd)
    if manifest_raw is None:
        raise VersionCheckError(f"head/{MANIFEST} is missing")
    try:
        json.loads(manifest_raw)
    except json.JSONDecodeError as exc:
        raise VersionCheckError(f"invalid {MANIFEST}: {exc.msg}") from exc

    # 规则语法用 base 检出中的 parser 校验（PR 无法通过携带恶意 parser 绕过）
    if rules_changed:
        rules_text = read_file(head_ref, HASH_RULES, cwd=cwd)
        if rules_text is None:
            raise VersionCheckError(f"head/{HASH_RULES} is missing")
        validate_rules_text(rules_text, HASH_RULES)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True); parser.add_argument("--head", required=True)
    parser.add_argument("--cwd", default=None, help="git 命令工作目录（测试用；生产默认当前目录）")
    args = parser.parse_args()
    try: check(args.base, args.head, cwd=args.cwd)
    except VersionCheckError as exc:
        print(f"resource version check failed:\n{exc}", file=sys.stderr); return 1
    print("Resource Version Check: passed"); return 0

if __name__ == "__main__": raise SystemExit(main())
