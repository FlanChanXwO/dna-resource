# -*- coding: utf-8 -*-
"""generate_resource_manifest 增量算法测试。

核心契约：
- 普通增量模式只处理 `git diff --name-status checkpoint..HEAD` 的文件；
- add/modify 只对受管文件计算 SHA（用 spy 验证不碰其他文件）；
- delete 只删 key，不做任何 SHA 计算；
- rename 删除旧 key，新路径按规则判断是否加入；
- 非受管文件完全不影响 file_hashes；
- 只改 version/alias 时 hash 不变、resource_version 更新；
- 序列化稳定：file_hashes 字典序、2 空格缩进、ensure_ascii=False、结尾换行。
"""
import json

import pytest

import generate_resource_manifest as gen
from hash_rules import HashRuleSet


def make_hash_spy():
    """包装真实 SHA 计算，记录被读取过的文件。"""
    calls: list[str] = []

    def fake_hash(path) -> str:
        calls.append(str(path))
        # 用路径本身派生伪哈希，测试只关心"是否被读取"，不关心值
        return f"hash-of-{str(path).replace(chr(92), '/')}"

    fake_hash.calls = calls
    return fake_hash


def rules_of(text: str) -> HashRuleSet:
    return HashRuleSet.parse(text)


class TestAdd:
    def test_new_managed_file_adds_one_hash(self):
        hashes = {"fonts/a.ttf": "old"}
        rules = rules_of("fonts/\n")
        changes = [("A", "fonts/new.bin", "")]
        h = make_hash_spy()
        gen.apply_changes(hashes, rules, changes, version="9", hash_fn=h)
        assert hashes == {"fonts/a.ttf": "old", "fonts/new.bin": "hash-of-fonts/new.bin"}
        assert h.calls == ["fonts/new.bin"]

    def test_new_unmanaged_file_ignored(self):
        hashes = {"fonts/a.ttf": "old"}
        rules = rules_of("fonts/\n")
        changes = [("A", "images/role_avatar/120101.png", "")]
        h = make_hash_spy()
        gen.apply_changes(hashes, rules, changes, version="9", hash_fn=h)
        assert hashes == {"fonts/a.ttf": "old"}
        assert h.calls == []


class TestModify:
    def test_modified_managed_file_rehashed_only_itself(self):
        hashes = {"fonts/a.ttf": "h1", "fonts/b.ttf": "h2", "fonts/c.ttf": "h3"}
        rules = rules_of("fonts/\n")
        changes = [("M", "fonts/b.ttf", "")]
        h = make_hash_spy()
        gen.apply_changes(hashes, rules, changes, version="9", hash_fn=h)
        assert hashes["fonts/b.ttf"] == "hash-of-fonts/b.ttf"
        # 其他文件内容未被读取，hash 保持原值
        assert hashes["fonts/a.ttf"] == "h1"
        assert hashes["fonts/c.ttf"] == "h3"
        assert h.calls == ["fonts/b.ttf"]

    def test_modified_unmanaged_file_ignored(self):
        hashes = {"fonts/a.ttf": "h1"}
        rules = rules_of("fonts/\n")
        changes = [("M", "alias/char_alias.json", "")]
        h = make_hash_spy()
        gen.apply_changes(hashes, rules, changes, version="9", hash_fn=h)
        assert hashes == {"fonts/a.ttf": "h1"}
        assert h.calls == []


class TestDelete:
    def test_deleted_managed_file_removes_key_without_hashing(self):
        hashes = {"fonts/a.ttf": "h1", "fonts/b.ttf": "h2"}
        rules = rules_of("fonts/\n")
        changes = [("D", "fonts/a.ttf", "")]
        h = make_hash_spy()
        gen.apply_changes(hashes, rules, changes, version="9", hash_fn=h)
        assert hashes == {"fonts/b.ttf": "h2"}
        assert h.calls == []  # 删除不做任何 SHA 计算

    def test_deleted_unmanaged_file_ignored(self):
        hashes = {"fonts/a.ttf": "h1"}
        rules = rules_of("fonts/\n")
        changes = [("D", "calendar/bg.jpg", "")]
        gen.apply_changes(hashes, rules, changes, version="9", hash_fn=make_hash_spy())
        assert hashes == {"fonts/a.ttf": "h1"}


class TestRename:
    def test_rename_managed_to_managed(self):
        hashes = {"fonts/a.ttf": "h1", "fonts/b.ttf": "h2"}
        rules = rules_of("fonts/\n")
        changes = [("R100", "fonts/a.ttf", "fonts/renamed.ttf")]
        h = make_hash_spy()
        gen.apply_changes(hashes, rules, changes, version="9", hash_fn=h)
        assert "fonts/a.ttf" not in hashes
        assert hashes["fonts/b.ttf"] == "h2"
        assert hashes["fonts/renamed.ttf"] == "hash-of-fonts/renamed.ttf"
        assert h.calls == ["fonts/renamed.ttf"]

    def test_rename_managed_to_unmanaged(self):
        hashes = {"fonts/a.ttf": "h1"}
        rules = rules_of("fonts/\n")
        changes = [("R100", "fonts/a.ttf", "images/x.png")]
        h = make_hash_spy()
        gen.apply_changes(hashes, rules, changes, version="9", hash_fn=h)
        assert hashes == {}
        assert h.calls == []

    def test_rename_unmanaged_to_managed(self):
        hashes = {}
        rules = rules_of("fonts/\n")
        changes = [("R100", "images/x.png", "fonts/a.ttf")]
        h = make_hash_spy()
        gen.apply_changes(hashes, rules, changes, version="9", hash_fn=h)
        assert hashes == {"fonts/a.ttf": "hash-of-fonts/a.ttf"}
        assert h.calls == ["fonts/a.ttf"]

    def test_rename_deleted_old_path(self):
        # 旧路径若曾被排除（不在 hashes），删除操作不应报错
        hashes = {}
        rules = rules_of("fonts/\n")
        changes = [("R100", "fonts/a.ttf", "fonts/b.ttf")]
        gen.apply_changes(hashes, rules, changes, version="9", hash_fn=make_hash_spy())
        assert hashes == {"fonts/b.ttf": "hash-of-fonts/b.ttf"}


class TestVersionOnly:
    def test_alias_and_version_change_keeps_hashes_updates_resource_version(self):
        hashes = {"fonts/a.ttf": "h1"}
        rules = rules_of("fonts/\n")
        changes = [("M", "alias/char_alias.json", ""), ("M", "version", "")]
        h = make_hash_spy()
        gen.apply_changes(hashes, rules, changes, version="9", hash_fn=h)
        assert hashes == {"fonts/a.ttf": "h1"}
        assert h.calls == []


class TestReconciliation:
    """规则变更模式：只枚举受管范围，未变化文件复用旧 hash。"""

    def test_added_directory_rule_hashes_new_files_only(self, tmp_path):
        # 目录里已有 a.png(已有 hash) 与 b.png(新进入范围)
        (tmp_path / "d").mkdir()
        (tmp_path / "d" / "a.png").write_bytes(b"a")
        (tmp_path / "d" / "b.png").write_bytes(b"b")
        hashes = {"d/a.png": "existing"}
        rules = rules_of("d/\n")
        changes: list[tuple] = []  # 规则变更本身不通过 diff 体现
        h = make_hash_spy()
        gen.reconcile_scope(hashes, rules, changes, root=tmp_path, hash_fn=h)
        assert hashes == {"d/a.png": "existing", "d/b.png": "hash-of-d/b.png"}
        assert h.calls == ["d/b.png"]

    def test_removed_rule_removes_hashes_without_reading(self, tmp_path):
        # keep/ 目录与其文件仍存在：范围内文件复用旧 hash
        (tmp_path / "keep").mkdir()
        (tmp_path / "keep" / "x.png").write_bytes(b"x")
        hashes = {"fonts/a.ttf": "h1", "keep/x.png": "h2"}
        rules = rules_of("keep/\n")  # fonts/ 规则被删掉
        changes: list[tuple] = []
        h = make_hash_spy()
        gen.reconcile_scope(hashes, rules, changes, root=tmp_path, hash_fn=h)
        assert hashes == {"keep/x.png": "h2"}
        assert h.calls == []

    def test_new_exclusion_removes_excluded_hashes(self, tmp_path):
        # 磁盘文件仍存在，但 .gitkeep 被新排除规则覆盖 → hash 移除且不读取内容
        (tmp_path / "d").mkdir()
        (tmp_path / "d" / "a.png").write_bytes(b"a")
        (tmp_path / "d" / ".gitkeep").write_bytes(b"")
        hashes = {"d/a.png": "h1", "d/.gitkeep": "h2"}
        rules = rules_of("d/\n!d/.gitkeep\n")
        changes: list[tuple] = []
        h = make_hash_spy()
        gen.reconcile_scope(hashes, rules, changes, root=tmp_path, hash_fn=h)
        assert hashes == {"d/a.png": "h1"}
        assert h.calls == []

    def test_file_deleted_on_disk_but_rule_changed(self, tmp_path):
        # 磁盘上已不存在的 d/gone.png 对应 hash 应被清理
        (tmp_path / "d").mkdir()
        (tmp_path / "d" / "a.png").write_bytes(b"a")
        hashes = {"d/a.png": "h1", "d/gone.png": "h2"}
        rules = rules_of("d/\n")
        changes: list[tuple] = []
        gen.reconcile_scope(hashes, rules, changes, root=tmp_path, hash_fn=make_hash_spy())
        assert hashes == {"d/a.png": "h1"}

    def test_modified_file_in_scope_gets_rehashed(self, tmp_path):
        (tmp_path / "d").mkdir()
        (tmp_path / "d" / "a.png").write_bytes(b"new content")
        hashes = {"d/a.png": "stale"}
        rules = rules_of("d/\n")
        changes = [("M", "d/a.png", "")]
        h = make_hash_spy()
        gen.reconcile_scope(hashes, rules, changes, root=tmp_path, hash_fn=h)
        assert hashes == {"d/a.png": "hash-of-d/a.png"}


class TestApplyChangesReconcileShared:
    def test_apply_changes_delegates_to_reconcile_when_rules_changed(self):
        # 规则文件出现在 changes 里时走 reconciliation 路径
        hashes = {"fonts/a.ttf": "h1"}
        rules = rules_of("fonts/\n")
        changes = [("A", ".resourcehashes", "")]
        h = make_hash_spy()

        def fake_reconcile(h_, r_, c_, root, hash_fn):
            fake_reconcile.called = True

        original = gen.reconcile_scope
        gen.reconcile_scope = fake_reconcile
        try:
            gen.apply_changes(hashes, rules, changes, version="9", hash_fn=h, root=".")
        finally:
            gen.reconcile_scope = original
        assert fake_reconcile.called
        assert h.calls == []


class TestVersionAndManifest:
    def test_generate_rebuilds_manifest_from_source_files_only(self, tmp_path):
        """manifest 必须可脱离旧 manifest，仅凭声明文件与资源重新生成。"""

        (tmp_path / "fonts").mkdir()
        (tmp_path / "textures").mkdir()
        (tmp_path / "fonts" / "keep.ttf").write_bytes(b"a")
        (tmp_path / "fonts" / "ignored.ttf").write_bytes(b"ignored")
        (tmp_path / "textures" / "card.png").write_bytes(b"b")
        (tmp_path / "version").write_text("10\n", encoding="utf-8")
        (tmp_path / "resource_contract.json").write_text(
            json.dumps(
                {
                    "format_version": 2,
                    "required_dirs": ["fonts", "textures"],
                    "required_files": ["fonts/keep.ttf"],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (tmp_path / ".resourcehashes").write_text(
            "fonts/\n!fonts/ignored.ttf\ntextures/card.png\n",
            encoding="utf-8",
        )

        manifest = json.loads(gen.generate(tmp_path))

        assert manifest == {
            "format_version": 2,
            "required_dirs": ["fonts", "textures"],
            "required_files": ["fonts/keep.ttf"],
            "resource_version": "10",
            "file_hashes": {
                "fonts/keep.ttf": (
                    "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb"
                ),
                "textures/card.png": (
                    "3e23e8160039594a33894f6564e1b1348bbd7a0088d42c4acb73eeaed59c009d"
                ),
            },
        }

    def test_incremental_generation_matches_full_rebuild(self, tmp_path):
        """增量模式只能是优化，输出必须与完整重建字节一致。"""

        (tmp_path / "fonts").mkdir()
        (tmp_path / "fonts" / "a.ttf").write_bytes(b"a")
        (tmp_path / "fonts" / "b.ttf").write_bytes(b"b")
        (tmp_path / "version").write_text("9\n", encoding="utf-8")
        (tmp_path / "resource_contract.json").write_text(
            json.dumps(
                {
                    "format_version": 2,
                    "required_dirs": ["fonts"],
                    "required_files": [],
                }
            ),
            encoding="utf-8",
        )
        (tmp_path / ".resourcehashes").write_text("fonts/\n", encoding="utf-8")
        (tmp_path / "resource_manifest.json").write_text(
            gen.generate(tmp_path),
            encoding="utf-8",
        )

        gen.git_output("init", cwd=tmp_path)
        gen.git_output("config", "user.name", "test", cwd=tmp_path)
        gen.git_output("config", "user.email", "test@example.com", cwd=tmp_path)
        gen.git_output("add", ".", cwd=tmp_path)
        gen.git_output("commit", "-m", "baseline", cwd=tmp_path)

        (tmp_path / "fonts" / "b.ttf").write_bytes(b"changed")
        (tmp_path / "version").write_text("10\n", encoding="utf-8")
        gen.git_output("add", "fonts/b.ttf", "version", cwd=tmp_path)
        gen.git_output("commit", "-m", "update resource", cwd=tmp_path)

        incremental = gen.generate_incremental(tmp_path)
        rebuilt = gen.generate(tmp_path)

        assert incremental == rebuilt

    def test_read_contract_requires_explicit_v2_policy(self, tmp_path):
        (tmp_path / "resource_contract.json").write_text(
            json.dumps(
                {
                    "format_version": 2,
                    "required_dirs": ["fonts", "data"],
                    "required_files": ["data/redeem_codes.json"],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        contract = gen.read_contract(tmp_path)

        assert contract == {
            "format_version": 2,
            "required_dirs": ["fonts", "data"],
            "required_files": ["data/redeem_codes.json"],
        }

    def test_resource_version_set_from_version_file(self):
        hashes: dict = {}
        rules = rules_of("fonts/\n")
        gen.apply_changes(hashes, rules, [], version="9", hash_fn=make_hash_spy())
        # apply_changes 不直接改 manifest；resource_version 由 update_manifest 设置
        manifest = {"format_version": 1, "required_dirs": ["fonts"], "resource_version": "8", "file_hashes": {}}
        gen.set_resource_version(manifest, "9")
        assert manifest["resource_version"] == "9"
        assert manifest["format_version"] == 1  # 契约字段不动

    def test_set_resource_version_rejects_non_positive_int(self):
        manifest = {"resource_version": "5"}
        with pytest.raises(ValueError):
            gen.set_resource_version(manifest, "0")
        with pytest.raises(ValueError):
            gen.set_resource_version(manifest, "abc")


class TestSerialize:
    def test_preserves_explicit_required_files_contract(self):
        manifest = {
            "format_version": 2,
            "required_dirs": ["fonts", "data"],
            "required_files": ["data/redeem_codes.json"],
            "file_hashes": {},
            "resource_version": "10",
        }

        out = gen.serialize(manifest)

        parsed = json.loads(out)
        assert parsed["format_version"] == 2
        assert parsed["required_files"] == ["data/redeem_codes.json"]

    def test_sorted_two_space_indent_no_ascii_escape_trailing_newline(self):
        manifest = {
            "format_version": 1,
            "required_dirs": ["fonts"],
            "file_hashes": {"fonts/b.ttf": "x", "fonts/a.ttf": "y", "字体/文.png": "z"},
            "resource_version": "7",
        }
        out = gen.serialize(manifest)
        assert out.endswith("\n")
        # ensure_ascii=False：中文字符原样输出
        assert "字体/文.png" in out
        # file_hashes 按路径字典序排序：键顺序在 JSON 文本中出现
        ia, ib = out.index('"fonts/a.ttf"'), out.index('"fonts/b.ttf"')
        assert ia < ib
        parsed = json.loads(out)
        assert list(parsed["file_hashes"]) == sorted(parsed["file_hashes"])

    def test_byte_identical_for_equal_input(self):
        m1 = {"format_version": 1, "required_dirs": ["fonts"], "resource_version": "7", "file_hashes": {"b": "2", "a": "1"}}
        m2 = {"file_hashes": {"a": "1", "b": "2"}, "resource_version": "7", "format_version": 1, "required_dirs": ["fonts"]}
        assert gen.serialize(m1) == gen.serialize(m2)
