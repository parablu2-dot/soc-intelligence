"""
BaseCrawler: 모든 축(axis)의 크롤러가 상속받는 공통 인터페이스.

새 소스 추가 시:
    1. crawlers/{axis}/{company}.py 생성
    2. BaseCrawler 상속, fetch()/parse() 구현
    3. config.yaml에 등록

LLM 개입 없이 결정론적으로 동작해야 한다 (requests/BeautifulSoup 등).
"""
from abc import ABC, abstractmethod
from pathlib import Path
import json

from .schema import RefinedSignal

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"
REFINED_DIR = Path(__file__).resolve().parents[2] / "data" / "refined"


class BaseCrawler(ABC):
    axis: str = ""       # 하위 클래스에서 지정
    company: str = ""    # 하위 클래스에서 지정

    @abstractmethod
    def fetch(self) -> str:
        """원본 소스에서 raw HTML/JSON을 가져온다. 여기서 dedupe/파싱 금지."""
        raise NotImplementedError

    @abstractmethod
    def parse(self, raw: str) -> list[RefinedSignal]:
        """raw 데이터를 RefinedSignal 리스트로 정규화한다."""
        raise NotImplementedError

    def run(self) -> list[RefinedSignal]:
        raw = self.fetch()
        self._save_raw(raw)
        signals = self.parse(raw)
        self._save_refined(signals)
        return signals

    def _save_raw(self, raw: str) -> None:
        out = RAW_DIR / self.axis / f"{self.company}.txt"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(raw, encoding="utf-8")

    def _save_refined(self, signals: list[RefinedSignal]) -> None:
        out = REFINED_DIR / self.axis / f"{self.company}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps([s.to_dict() for s in signals], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
