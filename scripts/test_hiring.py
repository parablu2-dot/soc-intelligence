"""채용 크롤러 검증 — SK하이닉스·Micron·Tesla 태그 확인."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from crawlers.hpc_datacenter.hiring import HiringCrawler

r = HiringCrawler().run()
print("Total:", len(r))

TARGETS = ("SK hynix", "Micron", "Tesla")
by_tag = {}
for s in r:
    for t in (s.tags or []):
        if t in TARGETS:
            by_tag[t] = by_tag.get(t, 0) + 1
for k, v in sorted(by_tag.items()):
    print("  [company tag] %s: %d" % (k, v))

print("\nSample with company tags:")
count = 0
for s in r:
    if s.tags and any(t in s.tags for t in TARGETS):
        print("  [%s] %s" % (", ".join(s.tags), s.headline[:68]))
        count += 1
        if count >= 8:
            break
if count == 0:
    print("  (no company-tagged signals yet — Google News query may need time)")
