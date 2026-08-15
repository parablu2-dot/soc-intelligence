"""CPO/광통신 축 Google News RSS 크롤러 — 공통 로직은 crawlers/common/googlenews_axis.py 참고.

OFC(ofcconference.org)는 RSS/API가 없어(Open Item 1 조사 결과) 전용 스크래퍼 대신 이 축 뉴스
쿼리(crawlers/config.yaml의 axis_news_queries.cpo_optics)로 OFC/CPO 업계 보도를 커버한다.
Baidu 차단 시 Google News zh로 대체한 20260717 선례와 동일한 판단."""
from crawlers.common.googlenews_axis import GoogleNewsAxisCrawler


class CpoOpticsGoogleNewsCrawler(GoogleNewsAxisCrawler):
    axis = "cpo_optics"


if __name__ == "__main__":
    CpoOpticsGoogleNewsCrawler().run()
