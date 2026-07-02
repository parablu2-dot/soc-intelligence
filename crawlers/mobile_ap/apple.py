"""Apple Newsroom RSS 크롤러 — A-series / M-series 칩 관련 신호 수집."""
from crawlers.common.base_crawler import BaseCrawler
from crawlers.common.rss_utils import (
    fetch_rss_raw, parse_rss, is_soc_relevant, extract_tags, infer_category
)
from crawlers.common.schema import RefinedSignal


class AppleCrawler(BaseCrawler):
    axis = "mobile_ap"
    company = "apple"

    RSS_URL = "https://www.apple.com/newsroom/rss-feed.rss"

    def fetch(self) -> str:
        return fetch_rss_raw(self.RSS_URL)

    def parse(self, raw: str) -> list[RefinedSignal]:
        signals = []
        for item in parse_rss(raw):
            combined = f"{item['title']} {item['summary']}"
            if not is_soc_relevant(combined):
                continue
            signals.append(RefinedSignal(
                axis=self.axis,
                company=self.company,
                category=infer_category(combined),
                headline=item["title"],
                url=item["url"],
                published_date=item["published_date"],
                source="Apple Newsroom",
                tags=extract_tags(combined),
                summary=item["summary"][:500] if item["summary"] else None,
            ))
        return signals


if __name__ == "__main__":
    AppleCrawler().run()
