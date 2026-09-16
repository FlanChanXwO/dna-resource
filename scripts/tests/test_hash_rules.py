# -*- coding: utf-8 -*-
"""HashRuleSet 规则解析与路径匹配测试。

`.resourcehashes` 第一版语法：
- 空行忽略，`#` 开头注释；
- `path/` 递归匹配目录；`path/file.ext` 匹配单文件；
- `!path` 排除规则；规则按顺序处理，最后一次命中决定结果；
- 不支持通配符（`*` `**` `?` 与字符组）；
- 所有路径必须为仓库相对 POSIX 路径，非法规则直接抛错。
"""
import pytest

from hash_rules import HashRuleError, HashRuleSet


class TestParsing:
    def test_empty_and_comments_ignored(self):
        rules = HashRuleSet.parse("# comment\n\n   \n# another\n")
        assert rules.lines == []

    def test_stores_rule_lines_in_order(self):
        rules = HashRuleSet.parse("calendar/\n!calendar/.gitkeep\nfonts/\n")
        assert rules.lines == ["calendar/", "!calendar/.gitkeep", "fonts/"]

    @pytest.mark.parametrize("bad", [
        "/abs/path",      # 绝对路径
        "../escape",      # .. 逃逸
        "foo/../bar",     # 内嵌 ..
        "foo\\bar",       # Windows 反斜杠
        "a/*/b",          # 通配符 *
        "a/**/b",         # 通配符 **
        "a?.png",         # 通配符 ?
        "a[bc].png",      # 字符组
    ])
    def test_invalid_rules_raise(self, bad):
        with pytest.raises(HashRuleError):
            HashRuleSet.parse(bad)

    def test_trailing_whitespace_is_stripped(self):
        rules = HashRuleSet.parse("fonts/   \n")
        assert rules.lines == ["fonts/"]


class TestMatching:
    def test_directory_recursive(self):
        rules = HashRuleSet.parse("textures/\n")
        assert rules.matches("textures/common/bg.jpg")
        assert rules.matches("textures/a/b/c.png")

    def test_single_file(self):
        rules = HashRuleSet.parse("calendar/banner_bg.webp\n")
        assert rules.matches("calendar/banner_bg.webp")
        assert not rules.matches("calendar/bg.jpg")

    def test_negation_excludes_file(self):
        rules = HashRuleSet.parse("calendar/\n!calendar/.gitkeep\n")
        assert rules.matches("calendar/bg.jpg")
        assert not rules.matches("calendar/.gitkeep")

    def test_last_match_wins(self):
        # 后规则覆盖前规则：目录先包含、子目录再排除，最终以最后命中的排除规则为准
        rules = HashRuleSet.parse("textures/\n!textures/cache/\n")
        assert rules.matches("textures/common/bg.jpg")
        assert not rules.matches("textures/cache/x.png")

    def test_unmatched_path(self):
        rules = HashRuleSet.parse("fonts/\n")
        assert not rules.matches("images/role_avatar/120101.png")

    def test_unicode_path(self):
        rules = HashRuleSet.parse("wiki/role/\n")
        assert rules.matches("wiki/role/贝蕾妮卡.webp")

    def test_prefix_boundary(self):
        # `fonts/` 不应误匹配 `fonts2/x.ttf` 这类前缀撞车路径
        rules = HashRuleSet.parse("fonts/\n")
        assert not rules.matches("fonts2/x.ttf")

    def test_scan_targets_directories(self):
        # 供规则变更 reconciliation 枚举受管范围：返回需要扫描的目录
        rules = HashRuleSet.parse("calendar/\n!calendar/.gitkeep\nfonts/\n")
        assert rules.scan_dirs() == ["calendar", "fonts"]
