"""Foundry 축 Google News RSS 크롤러 — 공통 로직은 crawlers/common/googlenews_axis.py 참고."""
from crawlers.common.googlenews_axis import GoogleNewsAxisCrawler


class FoundryGoogleNewsCrawler(GoogleNewsAxisCrawler):
    axis = "foundry"


if __name__ == "__main__":
    FoundryGoogleNewsCrawler().run()
