"""Mobile AP 축 Google News RSS 크롤러 — 공통 로직은 crawlers/common/googlenews_axis.py 참고."""
from crawlers.common.googlenews_axis import GoogleNewsAxisCrawler


class MobileApGoogleNewsCrawler(GoogleNewsAxisCrawler):
    axis = "mobile_ap"


if __name__ == "__main__":
    MobileApGoogleNewsCrawler().run()
