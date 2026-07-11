"""
config.yaml에 등록된 (enabled: true) 크롤러를 모두 실행.
GitHub Actions cron에서 이 스크립트만 호출하면 됨 (LLM 미개입).

사용법:
    python -m crawlers.run_all
"""
import importlib
import sys
from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).parent / "config.yaml"

# config.yaml의 크롤러 축만 순회 — dedup/eco_companies/axis_news_queries/hiring_targets/policy 등
# 비-axis 섹션은 크롤러 스펙이 아니므로 제외(섞어서 순회하면 spec이 dict가 아니라 크래시).
_CRAWLER_AXES = ["mobile_ap", "hpc_datacenter", "custom_soc", "foundry", "packaging"]


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_all() -> None:
    config = load_config()
    total, failed = 0, []

    for axis in _CRAWLER_AXES:
        companies = config.get(axis) or {}
        for company, spec in companies.items():
            if not spec or not spec.get("enabled"):
                continue
            total += 1
            try:
                mod = importlib.import_module(spec["module"])
                crawler_cls = getattr(mod, spec["class"])
                crawler_cls().run()
                print(f"[OK] {axis}/{company}")
            except Exception as e:
                failed.append((axis, company, str(e)))
                print(f"[FAIL] {axis}/{company}: {e}")

    print(f"\n실행: {total}건, 실패: {len(failed)}건")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    run_all()
