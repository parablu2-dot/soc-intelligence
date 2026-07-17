"""
공통 크롤링 유틸리티.
RSS/HTML 파싱, SoC 키워드 필터링, 카테고리 추론 함수 제공.
"""
import re
from datetime import date
from typing import Optional

import feedparser
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; SoCIntelligenceBot/1.0)"
    )
}

# 소문자 비교용 — is_soc_relevant에서만 사용
_SOC_KEYWORDS_LOWER = [
    "chip", "soc", "silicon", "semiconductor", "processor", "wafer",
    "2nm", "3nm", "4nm", "5nm", "n2 ", "n3 ", "n4 ", "n5 ", "angstrom",
    "nanometer", "process node",
    "tsmc", "samsung foundry", "intel foundry", "smic",
    "cowos", "ucie", "hbm", "chiplet", "3d ic", "advanced packaging",
    "integrated fan-out", "integrated fan out",
    "ai chip", "npu", "gpu", "trainium", "tpu", "maia", "asic",
    "mobile ap", "application processor", "bionic", "apple silicon",
    "snapdragon",
    "dimensity", "exynos", "kirin",
    "data center", "datacenter", "hpc", "accelerator",
    "foundry capacity", "fab capacity",
    # 한국어 키워드
    "반도체", "파운드리", "웨이퍼", "공정", "칩셋", "시스템반도체",
    "첨단패키징", "엑시노스", "퀄컴", "스냅드래곤", "미디어텍",
    "엔비디아", "에이엠디", "인텔", "삼성 파운드리", "tsmc",
    # 중국어(zh) 키워드 — Google News zh 소스(crawlers/tech/googlenews_zh.py)용, 20260717 후속
    "半导体", "芯片", "晶圆", "代工", "制程", "先进封装", "封装",
    "台积电", "三星", "英伟达", "英特尔", "高通", "联发科", "海思",
    "存储芯片", "存储器", "人工智能芯片",
]

# 채용 관련 키워드 — infer_category에서 사용 (단일 단어 "engineer" 등 광범위한 용어 제외)
_HIRING_KEYWORDS_LOWER = [
    "hiring", "job opening", "recruit", "talent acquisition",
    "r&d center opening", "new design center", "new research center",
    "expand workforce", "chip talent", "semiconductor talent",
    "engineer shortage", "talent shortage", "workforce expansion",
    "engineering jobs", "chip engineer hiring", "semiconductor hiring",
    "채용", "인재 영입", "고용", "구인",
]


def fetch_rss_raw(url: str, timeout: int = 30) -> str:
    """RSS/Atom 피드 원본 XML 텍스트를 반환한다."""
    resp = requests.get(url, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def fetch_html(url: str, timeout: int = 30) -> str:
    """HTML 페이지 원본을 반환한다."""
    resp = requests.get(url, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def parse_rss(raw: str) -> list[dict]:
    """RSS/Atom XML 텍스트를 파싱해 항목 딕셔너리 리스트를 반환한다."""
    feed = feedparser.parse(raw)
    items = []
    for entry in feed.entries:
        items.append({
            "title": strip_html(entry.get("title", "")),
            "url": entry.get("link", ""),
            "summary": strip_html(
                entry.get("summary", entry.get("description", ""))
            ),
            "published_date": _parse_entry_date(entry),
        })
    return items


def is_soc_relevant(text: str) -> bool:
    """SoC 관련 키워드 포함 여부를 반환한다."""
    lower = text.lower()
    return any(kw in lower for kw in _SOC_KEYWORDS_LOWER)


def extract_tags(text: str) -> Optional[list]:
    """텍스트에서 SoC 관련 태그를 추출한다."""
    lower = text.lower()
    found = []
    # 순서 중요: 더 구체적인 패턴을 먼저 검사
    checks = [
        ("HBM4", "hbm4"),
        ("HBM3E", "hbm3e"),
        ("HBM3", "hbm3"),
        ("HBM", "hbm"),
        ("CoWoS-L", "cowos-l"),
        ("CoWoS-S", "cowos-s"),
        ("CoWoS", "cowos"),
        ("UCIe", "ucie"),
        ("2nm", "2nm"),
        ("3nm", "3nm"),
        ("4nm", "4nm"),
        ("5nm", "5nm"),
        ("3D IC", "3d ic"),
        ("chiplet", "chiplet"),
        ("TSMC", "tsmc"),
        ("ASIC", "asic"),
        ("NPU", "npu"),
        ("Trainium", "trainium"),
        ("TPU", " tpu"),
        ("Maia", "maia"),
    ]
    seen = set()
    for tag, kw in checks:
        if kw in lower and tag not in seen:
            found.append(tag)
            seen.add(tag)
    # 대소문자 구분이 필요한 패턴
    if "InFO" in text or "Integrated Fan-Out" in text:
        found.append("InFO")
    return found if found else None


def infer_category(text: str) -> str:
    """텍스트에서 신호 카테고리(news/price/hiring/process/packaging)를 추론한다."""
    lower = text.lower()
    if any(k in lower for k in _HIRING_KEYWORDS_LOWER):
        return "hiring"
    if any(k in lower for k in ["wafer price", "pricing", "cost per wafer", "asm price"]):
        return "price"
    if any(k in lower for k in ["packaging", "cowos", "chiplet", "hbm", "3d ic", "ucie",
                                  "fan-out", "interposer"]):
        return "packaging"
    if any(k in lower for k in ["2nm", "3nm", "4nm", "5nm", "process node", "foundry",
                                  "tsmc", "fab", "nanometer", "n2", "n3"]):
        return "process"
    return "news"


def dedupe_by_title(items: list[dict]) -> list[dict]:
    """Google News 등 aggregator가 같은 기사를 발행처만 다르게(제목 끝 ' - 발행처')
    여러 건 반환하는 문제 완화. 제목 정규화 후 첫 등장만 남긴다 (URL은 원본 유지).
    dedup_gate.py의 임베딩 dedup(축+회사 스코프)과 별개로 크롤러 단계에서 먼저 걸러낸다."""
    seen: set[str] = set()
    out = []
    for item in items:
        norm = re.sub(r"\s*-\s*[^-]+$", "", item["title"]).strip().lower()
        norm = re.sub(r"[^\w\s]", "", norm)
        if norm in seen:
            continue
        seen.add(norm)
        out.append(item)
    return out


def strip_html(text: str) -> str:
    """HTML 태그를 제거한다."""
    if not text:
        return ""
    return BeautifulSoup(text, "lxml").get_text(separator=" ").strip()


def _parse_entry_date(entry) -> date:
    for field in ("published_parsed", "updated_parsed", "created_parsed"):
        val = getattr(entry, field, None)
        if val:
            try:
                return date(*val[:3])
            except Exception:
                pass
    return date.today()
