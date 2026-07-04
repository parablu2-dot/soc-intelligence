"""
반도체·AI칩 채용 레이더 크롤러 — HPC/AI 가속기 분야 인재 채용 신호 수집.
CHANGES-v3 spec #8: SK하이닉스·Micron·Tesla SoC 설계 채용 소스 명시 추가.
v3.1: config.yaml hiring_targets에서 ECO 업체 전체로 자동 확장.

소스:
  1. Semiconductor Engineering — 업계 인재 동향 전문
  2. EE Times — 전기전자 엔지니어 산업 뉴스
  3. Google News — 범용 반도체 채용 쿼리
  4. Google News — 기업별 특정 쿼리 (TSMC·Samsung·NVIDIA·AMD 설계센터)
  5. Google News — SK하이닉스 SoC 설계 채용 (spec #8)
  6. Google News — Micron 칩 설계 채용 (spec #8)
  7. Google News — Tesla FSD/Dojo 칩팀 채용 (spec #8)
  8+. Google News — config.yaml hiring_targets ECO 업체 (자동 생성)
"""
import urllib.parse
from pathlib import Path

import requests
import yaml

from crawlers.common.base_crawler import BaseCrawler
from crawlers.common.rss_utils import (
    HEADERS, parse_rss, extract_tags, infer_category
)
from crawlers.common.schema import RefinedSignal

# 채용 필터 — 이 크롤러 전용, rss_utils._HIRING_KEYWORDS_LOWER보다 넓게
_HIRING_KWS = [
    "hiring", "recruit", "talent", "job opening", "headcount",
    "r&d center", "design center", "new facility", "expand", "workforce",
    "talent shortage", "talent acquisition", "chip talent",
]

_FEEDS = [
    # ── 업계 미디어 ─────────────────────────────────────────────────────────
    {
        "url": "https://semiengineering.com/feed/",
        "source": "Semiconductor Engineering",
        "company_tag": None,
        "strict_filter": [
            "hiring", "recruit", "talent shortage", "workforce shortage",
            "chip talent", "headcount", "new design center", "r&d center opening",
            "job opening", "talent acquisition",
        ],
    },
    {
        "url": "https://www.eetimes.com/feed/",
        "source": "EE Times",
        "company_tag": None,
        "strict_filter": [
            "hiring", "recruit", "talent shortage", "job opening",
            "chip talent", "r&d center", "campus opening",
        ],
    },
    # ── 범용 반도체 채용 뉴스 ─────────────────────────────────────────────
    {
        "url": (
            "https://news.google.com/rss/search"
            "?q=semiconductor+chip+hiring+OR+recruit+OR+%22talent+shortage%22"
            "&hl=en-US&gl=US&ceid=US:en"
        ),
        "source": "Google News",
        "company_tag": None,
        "strict_filter": _HIRING_KWS,
    },
    {
        "url": (
            "https://news.google.com/rss/search"
            "?q=TSMC+OR+Samsung+OR+NVIDIA+OR+AMD+%22design+center%22+OR+%22R%26D+center%22"
            "&hl=en-US&gl=US&ceid=US:en"
        ),
        "source": "Google News",
        "company_tag": None,
        "strict_filter": _HIRING_KWS,
    },
    # ── spec #8: SK하이닉스 SoC 설계 채용 ──────────────────────────────────
    {
        "url": (
            "https://news.google.com/rss/search"
            "?q=%22SK+hynix%22+%22chip+design%22+OR+%22SoC%22+OR+%22semiconductor%22"
            "+hiring+OR+recruit+OR+%22design+center%22"
            "&hl=en-US&gl=US&ceid=US:en"
        ),
        "source": "Google News",
        "company_tag": "SK hynix",
        "strict_filter": _HIRING_KWS,
    },
    {
        "url": (
            "https://news.google.com/rss/search"
            "?q=%22SK%ED%95%98%EC%9D%B4%EB%8B%89%EC%8A%A4%22+%EC%B1%84%EC%9A%A9+OR+%EC%9D%B8%EC%9E%AC"
            "&hl=ko&gl=KR&ceid=KR:ko"
        ),
        "source": "Google News Korea",
        "company_tag": "SK hynix",
        "strict_filter": ["채용", "인재", "모집", "공고", "설계", "엔지니어"],
    },
    # ── spec #8: Micron 칩 설계 채용 ────────────────────────────────────────
    {
        "url": (
            "https://news.google.com/rss/search"
            "?q=Micron+Technology+%22chip+design%22+OR+%22memory+design%22+OR+%22SoC%22"
            "+hiring+OR+recruit+OR+%22design+center%22+OR+%22R%26D%22"
            "&hl=en-US&gl=US&ceid=US:en"
        ),
        "source": "Google News",
        "company_tag": "Micron",
        "strict_filter": _HIRING_KWS,
    },
    # ── spec #8: Tesla FSD·Dojo 칩팀 채용 ───────────────────────────────────
    {
        "url": (
            "https://news.google.com/rss/search"
            "?q=Tesla+%22FSD+chip%22+OR+%22Dojo%22+OR+%22autopilot+chip%22"
            "+hiring+OR+engineer+OR+%22design+center%22"
            "&hl=en-US&gl=US&ceid=US:en"
        ),
        "source": "Google News",
        "company_tag": "Tesla",
        "strict_filter": _HIRING_KWS + ["fsd", "dojo", "autopilot"],
    },
]

# 반도체 회사 키워드 — 관련 없는 기사 제거용
_COMPANY_KEYWORDS = [
    "semiconductor", "chip", "tsmc", "nvidia", "amd", "intel", "qualcomm",
    "broadcom", "apple", "samsung", "mediatek", "soc", "asic", "npu", "gpu",
    "foundry", "fab", "silicon", "hbm", "cowos", "ai accelerator",
    "sk hynix", "sk하이닉스", "micron", "tesla", "fsd", "dojo",
    "marvell", "globalfoundries", "ase group", "amkor", "jcet",
    "google", "meta", "anthropic", "openai", "tpu", "mtia",
]

# config.yaml 슬러그 → Google News 피드 company_tag 매핑
_SLUG_TO_TAG: dict[str, str] = {
    "tsmc": "TSMC",
    "samsung_foundry": "Samsung Foundry",
    "apple": "Apple",
    "nvidia": "NVIDIA",
    "amd": "AMD",
    "qualcomm": "Qualcomm",
    "broadcom": "Broadcom",
    "marvell": "Marvell",
    "mediatek": "MediaTek",
    "intel": "Intel",
    "intel_foundry": "Intel",
    "globalfoundries": "GlobalFoundries",
    "smic": "SMIC",
    "ase": "ASE",
    "amkor": "Amkor",
    "jcet": "JCET",
    "exynos": "Samsung",
    "hyperscaler_inhouse": "Hyperscaler",
    "google": "Google",
    "meta": "Meta",
    "anthropic": "Anthropic",
    "openai": "OpenAI",
}

_CFG_PATH = Path(__file__).resolve().parents[2] / "crawlers" / "config.yaml"


def _load_eco_feeds() -> list[dict]:
    """config.yaml hiring_targets → 동적 Google News 피드 생성."""
    try:
        cfg = yaml.safe_load(_CFG_PATH.read_text(encoding="utf-8"))
        targets: dict = cfg.get("hiring_targets", {})
    except Exception:
        return []
    feeds = []
    for slug, query in targets.items():
        encoded = urllib.parse.quote(query)
        feeds.append({
            "url": (
                f"https://news.google.com/rss/search"
                f"?q={encoded}&hl=en-US&gl=US&ceid=US:en"
            ),
            "source": "Google News",
            "company_tag": _SLUG_TO_TAG.get(slug, slug),
            "strict_filter": _HIRING_KWS,
        })
    return feeds


class HiringCrawler(BaseCrawler):
    axis = "hpc_datacenter"
    company = "hiring"

    def __init__(self) -> None:
        self._feeds = _FEEDS + _load_eco_feeds()

    def fetch(self) -> str:
        parts = []
        for feed in self._feeds:
            try:
                resp = requests.get(feed["url"], headers=HEADERS, timeout=30)
                resp.raise_for_status()
                tag = feed.get("company_tag") or ""
                parts.append(
                    f"### SOURCE:{feed['source']}||COTAG:{tag}||URL:{feed['url']} ###\n{resp.text}"
                )
            except Exception as e:
                parts.append(
                    f"### SOURCE:{feed['source']}||COTAG:||URL:{feed['url']} ### ERROR:{e}"
                )
        return "\n\n".join(parts)

    def parse(self, raw: str) -> list[RefinedSignal]:
        if not raw:
            return []
        signals = []
        seen_urls = set()
        blocks = raw.split("### SOURCE:")
        for block in blocks:
            if not block.strip():
                continue
            meta_line, _, xml_body = block.partition(" ###\n")
            if "ERROR:" in xml_body:
                continue

            parts_meta = meta_line.split("||")
            source_name = parts_meta[0].strip()
            company_tag = parts_meta[1].replace("COTAG:", "").strip() if len(parts_meta) > 1 else ""

            feed_conf = next(
                (f for f in self._feeds
                 if f["source"] == source_name
                 and (f.get("company_tag") or "") == company_tag),
                None,
            )
            hiring_kws = feed_conf["strict_filter"] if feed_conf else _HIRING_KWS

            for item in parse_rss(xml_body):
                if item["url"] in seen_urls:
                    continue
                combined = f"{item['title']} {item['summary']}".lower()

                has_hiring = any(kw in combined for kw in hiring_kws)
                has_company = any(kw in combined for kw in _COMPANY_KEYWORDS)
                if not (has_hiring and has_company):
                    continue

                full = f"{item['title']} {item['summary']}"
                category = infer_category(full)
                if category == "news":
                    category = "hiring"

                tags = extract_tags(full) or []
                # 기업 특정 피드 신호에 회사 태그 삽입
                if company_tag and company_tag not in tags:
                    tags.append(company_tag)

                seen_urls.add(item["url"])
                signals.append(RefinedSignal(
                    axis=self.axis,
                    company=self.company,
                    category=category,
                    headline=item["title"],
                    url=item["url"],
                    published_date=item["published_date"],
                    source=source_name,
                    tags=tags if tags else None,
                    summary=item["summary"][:500] if item["summary"] else None,
                ))
        return signals


if __name__ == "__main__":
    HiringCrawler().run()
