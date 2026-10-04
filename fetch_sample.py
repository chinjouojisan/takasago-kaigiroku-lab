# B12: ネットワークなし。本会議の議事録で「採決」がどう記録されているかを調べる(議員ごとの賛否が残るか)
import re, glob, os, io, datetime, unicodedata
from collections import Counter
def nf(s): return unicodedata.normalize("NFKC", s)
def sq(s): return re.sub(r"\s+", "", nf(s))
PH = {
 "起立": "起立", "賛成者": "賛成者", "全員賛成": "全員賛成", "賛成多数": "賛成多数", "賛成少数": "賛成少数",
 "全会一致": "全会一致", "異議なし": "異議なし", "異議ありません": "異議ありません", "記名投票": "記名投票",
 "反対討論": "反対討論", "賛成討論": "賛成討論", "討論を終": "討論を終", "討論なし": "討論なし",
 "挙手": "挙手", "投票": "投票", "賛成議員": "賛成議員", "反対議員": "反対議員",
}
tot = Counter(); days = Counter(); samples = {}
named = []   # 賛成・反対の議員名が列挙されていそうな箇所
for p in sorted(glob.glob("raw/minutes/R*A.txt")):
    fn = os.path.basename(p)[:-4]
    t = open(p, encoding="utf-8", errors="replace").read()
    s = sq(t)
    seen = set()
    for k, ph in PH.items():
        n = s.count(ph)
        if n:
            tot[k] += n
            if k not in seen: days[k] += 1; seen.add(k)
            if k not in samples or len(samples[k]) < 3:
                i = s.find(ph)
                samples.setdefault(k, []).append("%s: ...%s..." % (fn, s[max(0, i-60): i+80]))
    # 賛成議員・反対議員の名前の並び
    for m in re.finditer(r"(賛成|反対)(議員|者)?[はが、：:]?([^。]{0,120}議員[^。]{0,120})", s):
        if len(named) < 6: named.append("%s: %s" % (fn, m.group(0)[:200]))
out = io.StringIO()
out.write("生成 %s\n" % datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
out.write("--- 語句ごとの出現回数 / 出現した日数 ---\n")
for k in PH: out.write("%s %d回 / %d日\n" % (k, tot[k], days[k]))
out.write("--- 語句ごとの用例(最大3件) ---\n")
for k, v in samples.items():
    for x in v: out.write("[%s] %s\n" % (k, x))
out.write("--- 賛成・反対の議員名が並んでいそうな箇所(最大6件) ---\n")
for x in named: out.write(x + "\n")
open("raw/analysis/summary_votes_probe.txt", "w", encoding="utf-8").write(out.getvalue())
print("done")
