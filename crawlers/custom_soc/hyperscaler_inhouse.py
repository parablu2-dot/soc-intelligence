"""
하이퍼스케일러 인하우스 SoC 크롤러.
AWS Trainium / Google TPU / Microsoft Maia 관련 신호를 공식 블로그 RSS에서 수집.

소스:
  AWS  — https://aws.amazon.com/blogs/machine-learning/feed/
  Google — https://blog.google/technology/ai/rss/
  Microsoft — https://azure.microsoft.com/en-us/blog/feed/
"""
import requests

from crawlers.common.base_crawler import BaseCrawler
from crawlers.common.rss_utils import (
    HEADERS, parse_rss, is_soc_relevant, extract_tags, infer_category
)
from crawlers.common.schema import RefinedSignal

_FEEDS = [
    {
        "url": "https://aws.amazon.com/blogs/machine-learning/feed/",
        "source": "AWS Blog",
        "filter_keywords": ["trainium", "inferentia", "chip", "silicon", "asic"],
    },
    {
        "url": "https://blog.google/technology/ai/rss/",
        "source": "Google AI Blog",
        "filter_keywords": ["tpu", "tensor processing", "chip", "silicon", "asic"],
    },
    {
        "url": "https://azure.microsoft.com/en-us/blog/feed/",
        "source": "Microsoft Azure Blog",
        "filter_keywords": ["maia", "cobalt", "chip", "silicon", "asic", "accelerator"],
    },
]


class HyperscalerCrawler(BaseCrawler):
    axis = "custom_soc"
    company = "hyperscaler_inhouse"

    def fetch(self) -> str:
        # 3개 피드를 순서대로 연결한 단순 텍스트 묶음으로 저장
        parts = []
        for feed_conf in _FEEDS:
            try:
                resp = requests.get(feed_conf["url"], headers=HEADERS, timeout=30)
                resp.raise_for_status()
                parts.append(f"### SOURCE:{feed_conf['source']} ###\n{resp.text}")
            except Exception as e:
                parts.append(f"### SOURCE:{feed_conf['source']} ### ERROR:{e}")
        return "\n\n".join(parts)

    def parse(self, raw: str) -> list[RefinedSignal]:
        signals = []
        # ### SOURCE:xxx ### 구분자로 분할
        blocks = raw.split("### SOURCE:")
        for block in blocks:
            if not block.strip():
                continue
            first_line, _, xml_body = block.partition(" ###\n")
            source_name = first_line.strip()
            if "ERROR:" in xml_body:
                continue

            feed_conf = next(
                (f for f in _FEEDS if f["source"] == source_name), None
            )
            filter_kws = feed_conf["filter_keywords"] if feed_conf else []

            for item in parse_rss(xml_body):
                combined = f"{item['title']} {item['summary']}".lower()
                # 인하우스 칩 관련 키워드 또는 일반 SoC 키워드
                if not any(kw in combined for kw in filter_kws):
                    if not is_soc_relevant(f"{item['title']} {item['summary']}"):
                        continue

                full = f"{item['title']} {item['summary']}"
                signals.append(RefinedSignal(
                    axis=self.axis,
                    company=self.company,
                    category=infer_category(full),
                    headline=item["title"],
                    url=item["url"],
                    published_date=item["published_date"],
                    source=source_name,
                    tags=extract_tags(full),
                    summary=item["summary"][:500] if item["summary"] else None,
                ))
        return signals


if __name__ == "__main__":
    HyperscalerCrawler().run()
