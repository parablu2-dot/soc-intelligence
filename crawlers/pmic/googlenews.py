"""PMIC 축 Google News RSS 크롤러 — 공통 로직은 crawlers/common/googlenews_axis.py 참고.

기획 §8-1: 선단 노드 뉴스 사이클(2nm, HBM 세대 전환)에 PMIC는 거의 안 걸림 — 기존 축 쿼리를
공유하면 수집량이 0에 수렴할 위험이 있어 전용 쿼리(crawlers/config.yaml의
axis_news_queries.pmic)를 3갈래로 구성:
  1. 중국 파운드리 증설·레거시 라인 전환
  2. 아날로그 업체(TI/ADI/Infineon) 실적·가동률
  3. JEDEC DDR5 모듈 규격 관련
CPO 축 선례와 동일하게, 쿼리만으로는 부족해 crawlers/common/rss_utils.py의
_SOC_KEYWORDS_LOWER에 PMIC/아날로그 키워드를 추가했다(없으면 is_soc_relevant()가 필터링함)."""
from crawlers.common.googlenews_axis import GoogleNewsAxisCrawler


class PmicGoogleNewsCrawler(GoogleNewsAxisCrawler):
    axis = "pmic"


if __name__ == "__main__":
    PmicGoogleNewsCrawler().run()
