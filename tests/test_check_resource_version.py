# -*- coding: utf-8 -*-
"""check_resource_version 新规则测试（计划 §9）。

- docs-only 等纯维护变化：跳过，无需 bump；
- 资源变化：head version 必须 > base version；
- `.resourcehashes` 变化视为资源契约变化：必须 bump，且用 base 的 parser 校验语法；
- PR 中出现 resource_manifest.json：直接失败（合并后由 bot 自动生成）；
- 不再校验 PR 内 `resource_version == version`。
"""
import json
import subprocess

import pytest

import check_resource_version as chk


def git(cwd, *args: str) -> str:
    out = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    if out.returncode != 0:
        raise RuntimeError(out.stderr)
    return out.stdout


def make_repo(tmp_path, version="6", manifest_resource_version="6"):
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "config", "user.email", "t@t")
    git(tmp_path, "config", "user.name", "t")
    (tmp_path / "version").write_text(f"{version}\n")
    (tmp_path / "resource_manifest.json").write_text(json.dumps({
        "format_version": 1, "required_dirs": ["fonts"],
        "resource_version": manifest_resource_version, "file_hashes": {},
    }))
    (tmp_path / ".resourcehashes").write_text("fonts/\n")
    (tmp_path / "fonts").mkdir()
    (tmp_path / "README.md").write_text("readme\n")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "base")
    return tmp_path


def commit_all(tmp_path, msg="change"):
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", msg)


def run_check(base_ref, head_ref, cwd):
    return chk.check(base_ref, head_ref, cwd=str(cwd))


class TestDocsOnly:
    def test_docs_only_no_bump_needed(self, tmp_path):
        make_repo(tmp_path)
        git(tmp_path, "checkout", "-qb", "pr")
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "x.md").write_text("doc\n")
        commit_all(tmp_path)
        run_check("main", "pr", tmp_path)  # 不抛错即通过


class TestResourceChanges:
    def test_resource_change_requires_bump(self, tmp_path):
        make_repo(tmp_path)
        git(tmp_path, "checkout", "-qb", "pr")
        (tmp_path / "fonts" / "new.ttf").write_text("x")
        (tmp_path / "version").write_text("7\n")
        commit_all(tmp_path)
        run_check("main", "pr", tmp_path)

    def test_resource_change_without_bump_fails(self, tmp_path):
        make_repo(tmp_path)
        git(tmp_path, "checkout", "-qb", "pr")
        (tmp_path / "fonts" / "new.ttf").write_text("x")
        commit_all(tmp_path)
        with pytest.raises(chk.VersionCheckError):
            run_check("main", "pr", tmp_path)

    def test_non_increasing_version_fails(self, tmp_path):
        make_repo(tmp_path)
        git(tmp_path, "checkout", "-qb", "pr")
        (tmp_path / "fonts" / "new.ttf").write_text("x")
        (tmp_path / "version").write_text("5\n")  # 比 base 6 还小
        commit_all(tmp_path)
        with pytest.raises(chk.VersionCheckError):
            run_check("main", "pr", tmp_path)

    def test_manifest_still_required_to_exist_and_be_valid_json(self, tmp_path):
        make_repo(tmp_path)
        git(tmp_path, "checkout", "-qb", "pr")
        (tmp_path / "fonts" / "new.ttf").write_text("x")
        (tmp_path / "version").write_text("7\n")
        (tmp_path / "resource_manifest.json").write_text("{broken")
        commit_all(tmp_path)
        with pytest.raises(chk.VersionCheckError):
            run_check("main", "pr", tmp_path)


class TestManifestEditForbidden:
    def test_pr_touching_manifest_fails_even_with_bump(self, tmp_path):
        make_repo(tmp_path)
        git(tmp_path, "checkout", "-qb", "pr")
        (tmp_path / "version").write_text("7\n")
        m = json.loads((tmp_path / "resource_manifest.json").read_text())
        m["resource_version"] = "7"
        (tmp_path / "resource_manifest.json").write_text(json.dumps(m))
        commit_all(tmp_path)
        with pytest.raises(chk.VersionCheckError, match="generated automatically"):
            run_check("main", "pr", tmp_path)


class TestResourceHashes:
    def test_rules_change_requires_bump(self, tmp_path):
        make_repo(tmp_path)
        git(tmp_path, "checkout", "-qb", "pr")
        (tmp_path / ".resourcehashes").write_text("fonts/\ntextures/\n")
        (tmp_path / "version").write_text("7\n")
        commit_all(tmp_path)
        run_check("main", "pr", tmp_path)

    def test_rules_change_without_bump_fails(self, tmp_path):
        make_repo(tmp_path)
        git(tmp_path, "checkout", "-qb", "pr")
        (tmp_path / ".resourcehashes").write_text("fonts/\ntextures/\n")
        commit_all(tmp_path)
        with pytest.raises(chk.VersionCheckError):
            run_check("main", "pr", tmp_path)

    def test_invalid_rules_fail_with_base_parser(self, tmp_path):
        make_repo(tmp_path)
        git(tmp_path, "checkout", "-qb", "pr")
        (tmp_path / ".resourcehashes").write_text("fonts/\n/absolute/bad\n")
        (tmp_path / "version").write_text("7\n")
        commit_all(tmp_path)
        with pytest.raises(chk.VersionCheckError, match="resourcehashes"):
            run_check("main", "pr", tmp_path)


class TestMaintenanceFiles:
    def test_tests_dir_is_maintenance_exempt(self, tmp_path):
        # tests/ 属于仓库维护内容：新增测试无需 bump version
        make_repo(tmp_path)
        git(tmp_path, "checkout", "-qb", "pr")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_x.py").write_text("def test_x(): pass\n")
        commit_all(tmp_path)
        run_check("main", "pr", tmp_path)  # 不抛错即通过
