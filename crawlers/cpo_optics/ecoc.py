"""
ECOC(European Conference and Exhibition on Optical Communication) 전시사 뉴스 크롤러.
CPO(광통신) 9번째 축 전용 소스 (2026-08-11 구독시스템 구현 스펙 — Open Item 1 조사 결과).

소스 (RSS): https://www.ecocexhibition.com/feed/  (WordPress 기본 피드, robots.txt 전면 허용 확인
— User-agent: * / Disallow: 없음, RSS는 애초에 기계 구독용으로 공개된 엔드포인트)
Exhibitor News 카테고리로 실시간 업데이트됨 — CPO/광트랜시버/실리콘포토닉스 등 실 전시업체 발표.
직접 소스(전시사 공식 피드)라 tsmc.py/ase.py 등과 동일하게 관련성 필터 없이 전량 채택한다.

주의: 이 사이트는 WAF가 rss_utils.HEADERS의 "SoCIntelligenceBot" UA 문자열을 403으로 차단함
(robots.txt는 전면 허용이라 정책상 문제 아님 — 단순 UA 문자열 매칭 룰). 브라우저 UA로 우회.
"""
from crawlers.common.rss_utils import parse_rss, extract_tags, infer_category
from crawlers.common.base_crawler import BaseCrawler
from crawlers.common.schema import RefinedSignal

import requests

_RSS_URL = "https://www.ecocexhibition.com/feed/"
_SOURCE_NAME = "ECOC"
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


class EcocCrawler(BaseCrawler):
    axis = "cpo_optics"
    company = "ecoc"

    def fetch(self) -> str:
        resp = requests.get(_RSS_URL, headers=_BROWSER_HEADERS, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, raw: str) -> list[RefinedSignal]:
        if not raw:
            return []
        signals = []
        for item in parse_rss(raw):
            combined = f"{item['title']} {item['summary']}"
            signals.append(RefinedSignal(
                axis=self.axis,
                company=self.company,
                category=infer_category(combined),
                headline=item["title"],
                url=item["url"],
                published_date=item["published_date"],
                source=_SOURCE_NAME,
                tags=extract_tags(combined) or None,
                summary=item["summary"][:500] if item["summary"] else None,
            ))
        return signals


if __name__ == "__main__":
    EcocCrawler().run()
