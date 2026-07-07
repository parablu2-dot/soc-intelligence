"""Packaging 축 Google News RSS 크롤러 — 공통 로직은 crawlers/common/googlenews_axis.py 참고."""
from crawlers.common.googlenews_axis import GoogleNewsAxisCrawler


class PackagingGoogleNewsCrawler(GoogleNewsAxisCrawler):
    axis = "packaging"


if __name__ == "__main__":
    PackagingGoogleNewsCrawler().run()
