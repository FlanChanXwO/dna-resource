#!/usr/bin/env python3
import argparse, json, re, subprocess, sys

PATTERN = re.compile(r"^[1-9][0-9]*$")

class VersionCheckError(Exception):
    pass

def read_file(ref: str, path: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "show", f"{ref}:{path}"], text=True, stderr=subprocess.DEVNULL
        )
    except subprocess.CalledProcessError:
        return None

def parse_version(raw: str) -> int:
    value = raw[:-1] if raw.endswith("\n") else raw
    if not PATTERN.fullmatch(value):
        raise VersionCheckError(f'invalid version: "{value}"\nexpected positive decimal integer')
    return int(value)

def check(base_ref: str, head_ref: str) -> None:
    base_raw, head_raw = read_file(base_ref, "version"), read_file(head_ref, "version")
    if head_raw is None:
        raise VersionCheckError("head/version is missing")
    head = parse_version(head_raw)
    if base_raw is None:
        if head != 1:
            raise VersionCheckError(f"initial migration must use version 1, got {head}")
    elif head <= parse_version(base_raw):
        raise VersionCheckError(f"head version {head} must be greater than base version {parse_version(base_raw)}")
    manifest_raw = read_file(head_ref, "resource_manifest.json")
    if manifest_raw is None:
        raise VersionCheckError("head/resource_manifest.json is missing")
    try:
        manifest = json.loads(manifest_raw)
    except json.JSONDecodeError as exc:
        raise VersionCheckError(f"invalid resource_manifest.json: {exc.msg}") from exc
    value = manifest.get("resource_version") if isinstance(manifest, dict) else None
    if not isinstance(value, str) or not PATTERN.fullmatch(value):
        raise VersionCheckError("resource_manifest.json.resource_version must be a positive decimal string")
    if value != str(head):
        raise VersionCheckError(f"version file is {head} but resource_manifest.json.resource_version is {value!r}")

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True); parser.add_argument("--head", required=True)
    args = parser.parse_args()
    try: check(args.base, args.head)
    except VersionCheckError as exc:
        print(f"resource version check failed:\n{exc}", file=sys.stderr); return 1
    print("Resource Version: passed"); return 0

if __name__ == "__main__": raise SystemExit(main())
