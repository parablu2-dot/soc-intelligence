"""
export_baseline_notes.py — data/baseline/notes/*.md → data/refined/baseline_notes.json

장문 deep-research 노트(DistillationNote baseline 층)를 빌드타임에 파싱해 프론트가 fetch할 수 있는
JSON 매니페스트로 변환한다. LLM 호출 없음 — frontmatter 파싱 + 본문 그대로 전달뿐 (runtime-token-zero 유지).
append-only 원천: 이 스크립트는 data/baseline/notes/*.md 를 읽기만 하며 수정하지 않는다.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
NOTES_DIR = ROOT / "data" / "baseline" / "notes"
OUT_PATH = ROOT / "data" / "refined" / "baseline_notes.json"

_FRONTMATTER_RE = re.compile(r"^---\n(.*?\n)---\n(.*)$", re.DOTALL)
_H1_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)


def _parse_note(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    m = _FRONTMATTER_RE.match(raw)
    if m:
        meta = yaml.safe_load(m.group(1)) or {}
        body = m.group(2).strip()
    else:
        meta = {}
        body = raw.strip()

    h1 = _H1_RE.search(body)
    title = h1.group(1).strip() if h1 else path.stem

    return {
        "id": path.stem,
        "topic": meta.get("topic") or title,
        "axis": meta.get("axis") or meta.get("layer") or "",
        "status": str(meta.get("status") or ""),
        "tags": meta.get("tags") or [],
        "date": str(meta.get("date")) if meta.get("date") else "",
        "source": meta.get("source") or "",
        "graduation_gate": meta.get("graduation_gate") or "",
        "body_md": body,
    }


def run() -> None:
    if not NOTES_DIR.exists():
        print("[export_baseline_notes] data/baseline/notes/ 없음 — 스킵")
        return

    md_files = sorted(NOTES_DIR.glob("*.md"))
    notes = [_parse_note(p) for p in md_files]

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps({"notes": notes}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[export_baseline_notes] {len(notes)}건 → {OUT_PATH}")


if __name__ == "__main__":
    sys.exit(run())
