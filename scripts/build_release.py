"""Build portable release archive dist/dao-den-long-v1.0.0-portable.zip."""

from __future__ import annotations

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_ZIP = ROOT / "dist" / "dao-den-long-v1.0.0-portable.zip"
ROOT_FILES = (
    "game.contract.json",
    "README.md",
    "LICENSE",
    "CREDITS.md",
    "CHANGELOG.md",
    "run.sh",
    "run.bat",
    "Dockerfile",
)
INCLUDE_DIRS = ("src", "web")


def _add_file(zf: zipfile.ZipFile, src_path: Path, arc_name: str, executable: bool = False) -> None:
    data = src_path.read_bytes()
    info = zipfile.ZipInfo(arc_name)
    info.create_system = 3  # UNIX attributes preserved when unzipped on Linux/macOS
    info.compress_type = zipfile.ZIP_DEFLATED
    mode = 0o755 if executable else 0o644
    info.external_attr = (0o100000 | mode) << 16
    zf.writestr(info, data)


def main() -> int:
    OUT_ZIP.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    prefix = "dao-den-long-v1.0.0"

    with zipfile.ZipFile(OUT_ZIP, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel_name in ROOT_FILES:
            src_file = ROOT / rel_name
            if not src_file.is_file():
                raise FileNotFoundError(f"Missing release root file: {src_file}")
            _add_file(zf, src_file, f"{prefix}/{rel_name}", executable=(rel_name == "run.sh"))
            count += 1

        for dir_name in INCLUDE_DIRS:
            base = ROOT / dir_name
            for path in sorted(base.rglob("*")):
                if not path.is_file():
                    continue
                if "__pycache__" in path.parts or path.suffix in (".pyc", ".pyo"):
                    continue
                rel = path.relative_to(ROOT).as_posix()
                _add_file(zf, path, f"{prefix}/{rel}")
                count += 1

    size_kb = OUT_ZIP.stat().st_size / 1024.0
    print(f"Built {OUT_ZIP} ({count} files, {size_kb:.1f} KiB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
