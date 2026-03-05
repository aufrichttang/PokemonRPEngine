from __future__ import annotations

from pathlib import Path

SUSPECT_TOKENS = [
    "\u9386",  # 鎆-like mojibake family
    "\u93ba",  # 鎺
    "\u934f",  # 鍏
    "\u6d93",  # 涓 (often appears in mojibake text chunks)
    "\u7ed4",  # 绔
    "\u598d",  # 妭
    "\ufffd",  # replacement character
]
SCAN_EXT = {".py", ".ts", ".tsx", ".md", ".json", ".yml", ".yaml"}
SKIP_DIRS = {".git", ".pytest_cache", ".mypy_cache", "node_modules", "dist", "build"}


def iter_files(root: Path):
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.name == "check_mojibake.py":
            continue
        if p.suffix.lower() in SCAN_EXT:
            yield p


def main() -> int:
    root = Path(".").resolve()
    bad: list[tuple[Path, str]] = []
    for path in iter_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        for token in SUSPECT_TOKENS:
            if token in text:
                bad.append((path, token))
                break
    if bad:
        print("mojibake detected:")
        for path, token in bad:
            print(f"- {path}: token={repr(token)}")
        return 1
    print("mojibake check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
