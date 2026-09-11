#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_OUTPUT = Path("videos/login/background.mp4")


class PrepareError(RuntimeError):
    pass


def require_tool(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise PrepareError(f"Required tool not found in PATH: {name}")
    return path


def run_checked(args: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown error"
        raise PrepareError(f"Command failed: {' '.join(args)}\n{detail}")
    return result


def probe_video(ffprobe: str, path: Path) -> dict[str, object]:
    result = run_checked(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_name,width,height,avg_frame_rate",
            "-of",
            "json",
            str(path),
        ]
    )
    try:
        payload = json.loads(result.stdout)
        stream = payload["streams"][0]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise PrepareError(f"Unable to inspect video stream: {path}") from exc

    codec = stream.get("codec_name")
    if codec != "h264":
        raise PrepareError(
            f"Unsupported video codec: {codec!r}. Expected H.264; this tool never transcodes."
        )

    return {
        "codec": codec,
        "width": stream.get("width"),
        "height": stream.get("height"),
        "frame_rate": stream.get("avg_frame_rate"),
    }


def h264_sha256(ffmpeg: str, path: Path) -> str:
    process = subprocess.Popen(
        [
            ffmpeg,
            "-v",
            "error",
            "-i",
            str(path),
            "-map",
            "0:v:0",
            "-c:v",
            "copy",
            "-bsf:v",
            "h264_mp4toannexb",
            "-f",
            "h264",
            "pipe:1",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert process.stdout is not None
    assert process.stderr is not None

    digest = hashlib.sha256()
    while True:
        chunk = process.stdout.read(1024 * 1024)
        if not chunk:
            break
        digest.update(chunk)

    stderr = process.stderr.read().decode("utf-8", errors="replace").strip()
    returncode = process.wait()
    if returncode != 0:
        raise PrepareError(f"Failed to hash H.264 stream for {path}: {stderr}")
    return digest.hexdigest()


def top_level_atoms(path: Path) -> list[tuple[str, int, int]]:
    file_size = path.stat().st_size
    atoms: list[tuple[str, int, int]] = []
    offset = 0

    with path.open("rb") as handle:
        while offset + 8 <= file_size:
            handle.seek(offset)
            header = handle.read(8)
            if len(header) != 8:
                break

            size32, atom_type_raw = struct.unpack(">I4s", header)
            header_size = 8
            if size32 == 1:
                extended = handle.read(8)
                if len(extended) != 8:
                    raise PrepareError(f"Invalid extended MP4 atom at offset {offset}")
                atom_size = struct.unpack(">Q", extended)[0]
                header_size = 16
            elif size32 == 0:
                atom_size = file_size - offset
            else:
                atom_size = size32

            if atom_size < header_size or offset + atom_size > file_size:
                raise PrepareError(f"Invalid MP4 atom size at offset {offset}: {atom_size}")

            atom_type = atom_type_raw.decode("ascii", errors="replace")
            atoms.append((atom_type, offset, atom_size))
            offset += atom_size

    return atoms


def atom_offset(atoms: list[tuple[str, int, int]], atom_type: str) -> int:
    for current_type, offset, _ in atoms:
        if current_type == atom_type:
            return offset
    raise PrepareError(f"Required MP4 atom not found: {atom_type}")


def prepare(source: Path, output: Path) -> None:
    ffmpeg = require_tool("ffmpeg")
    ffprobe = require_tool("ffprobe")

    source = source.expanduser().resolve()
    output = output.expanduser().resolve()
    if not source.is_file():
        raise PrepareError(f"Source video not found: {source}")

    output.parent.mkdir(parents=True, exist_ok=True)
    source_info = probe_video(ffprobe, source)
    source_hash = h264_sha256(ffmpeg, source)

    temp_handle = tempfile.NamedTemporaryFile(
        prefix=".background.", suffix=".mp4", dir=output.parent, delete=False
    )
    temp_path = Path(temp_handle.name)
    temp_handle.close()

    try:
        run_checked(
            [
                ffmpeg,
                "-y",
                "-v",
                "error",
                "-i",
                str(source),
                "-map",
                "0:v:0",
                "-c:v",
                "copy",
                "-an",
                "-movflags",
                "+faststart",
                str(temp_path),
            ]
        )

        output_info = probe_video(ffprobe, temp_path)
        output_hash = h264_sha256(ffmpeg, temp_path)
        atoms = top_level_atoms(temp_path)
        moov_offset = atom_offset(atoms, "moov")
        mdat_offset = atom_offset(atoms, "mdat")

        if source_hash != output_hash:
            raise PrepareError(
                "H.264 stream hash changed after remux; refusing to replace the output file."
            )
        if source_info != output_info:
            raise PrepareError(
                f"Video metadata changed after remux: source={source_info}, output={output_info}"
            )
        if moov_offset >= mdat_offset:
            raise PrepareError(
                f"Fast Start verification failed: moov={moov_offset}, mdat={mdat_offset}"
            )

        os.replace(temp_path, output)
        print(f"Prepared: {output}")
        print(f"Size: {output.stat().st_size} bytes")
        print(f"H.264 SHA-256: {output_hash}")
        print(f"moov offset: {moov_offset}")
        print(f"mdat offset: {mdat_offset}")
        print("Video stream is unchanged and Fast Start is enabled.")
    finally:
        if temp_path.exists():
            temp_path.unlink()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare the login background MP4 for web playback using lossless H.264 remuxing."
        )
    )
    parser.add_argument("source", type=Path, help="source MP4 to prepare")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"output path (default: {DEFAULT_OUTPUT})",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        prepare(args.source, args.output)
    except PrepareError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
