# -*- coding: utf-8 -*-
"""`.resourcehashes` 规则解析与路径匹配。

第一版语法（刻意不实现完整 gitignore glob）：
- 空行忽略；`#` 开头为注释；
- `path/`：递归匹配目录；`path/file.ext`：匹配单文件；
- `!path`：排除规则；规则按顺序处理，最后一次命中决定结果；
- 不支持 `*` `**` `?` 与字符组；
- 所有路径必须为仓库相对 POSIX 路径，非法规则直接抛错（fail fast）。
"""
from __future__ import annotations

from dataclasses import dataclass, field

_FORBIDDEN_CHARS = set("*?[]")


class HashRuleError(ValueError):
    """`.resourcehashes` 规则语法非法。"""


def _validate_path(path: str) -> None:
    """校验单条规则路径：仓库相对、POSIX 分隔、无 .. 逃逸、无通配符。"""
    if path.startswith("/"):
        raise HashRuleError(f"absolute path not allowed: {path!r}")
    if "\\" in path:
        raise HashRuleError(f"windows path separator not allowed: {path!r}")
    if any(c in path for c in _FORBIDDEN_CHARS):
        raise HashRuleError(f"wildcards not supported: {path!r}")
    parts = [p for p in path.split("/") if p]
    if not parts:
        raise HashRuleError(f"empty path: {path!r}")
    if any(p == ".." for p in parts):
        raise HashRuleError(f".. escape not allowed: {path!r}")


@dataclass
class _Rule:
    include: bool  # True=包含，False=排除（`!` 前缀）
    path: str      # 去掉 `!` 后的路径；目录规则带尾部 `/`


@dataclass
class HashRuleSet:
    """有序规则集合；`matches` 按最后命中规则决定结果。

    `lines` 保存归一化（strip 后）的规则原文，用于规则文件对比与调试。
    """

    rules: list[_Rule] = field(default_factory=list)
    lines: list[str] = field(default_factory=list)

    @classmethod
    def parse(cls, text: str) -> "HashRuleSet":
        rules: list[_Rule] = []
        lines: list[str] = []
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            include = True
            path = line
            if path.startswith("!"):
                include = False
                path = path[1:]
            _validate_path(path)
            rules.append(_Rule(include=include, path=path))
            lines.append(line)
        return cls(rules=rules, lines=lines)

    def _match(self, path: str) -> _Rule | None:
        """返回最后一条命中的规则；未命中返回 None。"""
        hit: _Rule | None = None
        for rule in self.rules:
            if self._rule_matches(rule, path):
                hit = rule
        return hit

    def _rule_matches(self, rule: _Rule, path: str) -> bool:
        if rule.path.endswith("/"):
            # 目录规则：路径位于该目录之下（前缀 + 边界），等价于 glob `dir/**`
            prefix = rule.path
            return path.startswith(prefix)
        return path == rule.path

    def matches(self, path: str) -> bool:
        """给定仓库相对 POSIX 路径，判断是否受哈希管理。"""
        hit = self._match(path)
        return hit.include if hit is not None else False

    def scan_dirs(self) -> list[str]:
        """返回需要枚举扫描的目录（供规则变更 reconciliation 使用）。

        取所有包含规则中的目录前缀（去掉尾部 `/`，去重保序）；
        排除规则交给 `matches` 二次过滤。
        """
        dirs: list[str] = []
        for rule in self.rules:
            if rule.include and rule.path.endswith("/"):
                name = rule.path.rstrip("/")
                if name not in dirs:
                    dirs.append(name)
        return dirs

    def scan_files(self) -> list[str]:
        """返回包含规则中的单文件路径（去重保序），供 reconciliation 枚举。"""
        files: list[str] = []
        for rule in self.rules:
            if rule.include and not rule.path.endswith("/"):
                if rule.path not in files:
                    files.append(rule.path)
        return files
