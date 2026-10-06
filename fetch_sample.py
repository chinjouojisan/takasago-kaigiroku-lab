# B20: 選管の選挙結果ページを1回だけ取得し、表を読み取って議員IDと突き合わせる
# 取得: https://www.city.takasago.lg.jp/soshikikarasagasu/senkyokanriiinkaijimukyoku/2/1/12717.html (1回のみ。robots.txtを確認)
# 出力: raw/senkyo/takasago_2022_senkyo.html(原本), raw/analysis/election_2022.csv, summary_election_v1.txt
import csv, html, os, re, sys, time, unicodedata, urllib.request
from urllib.robotparser import RobotFileParser
URL = "https://www.city.takasago.lg.jp/soshikikarasagasu/senkyokanriiinkaijimukyoku/2/1/12717.html"
UA = "takasago-giin-map-research/0.6 (civic data research, low rate)"
os.makedirs("raw/senkyo", exist_ok=True); os.makedirs("raw/analysis", exist_ok=True)
ROSTER = {"M001":"石崎徹","M002":"入江啓太","M003":"今竹大祐","M004":"岩見明","M005":"大西由紀","M006":"川端宏明","M007":"北野誠一郎","M008":"坂本まり","M009":"迫川高行","M010":"芝本鎮彰","M011":"島津明香","M012":"鈴木利信","M013":"鷹尾治久","M014":"春増勝利","M015":"藤森誠","M016":"松野優也","M017":"森秀樹","M018":"山田光昭","M019":"横田英樹"}
# 名字(漢字, 読み): 選管の表記が仮名まじりのため、名字の先頭一致で突き合わせる(結果は要約に出して人が確認)
SURN = {"M001":("石崎","いしざき"),"M002":("入江","いりえ"),"M003":("今竹","いまたけ"),"M004":("岩見","いわみ"),"M005":("大西","おおにし"),"M006":("川端","かわばた"),"M007":("北野","きたの"),"M008":("坂本","さかもと"),"M009":("迫川","さこがわ"),"M010":("芝本","しばもと"),"M011":("島津","しまづ"),"M012":("鈴木","すずき"),"M013":("鷹尾","たかお"),"M014":("春増","はるまし"),"M015":("藤森","ふじもり"),"M016":("松野","まつの"),"M017":("森","もり"),"M018":("山田","やまだ"),"M019":("横田","よこた")}
path = "raw/senkyo/takasago_2022_senkyo.html"
if not os.path.exists(path):
    rp = RobotFileParser("https://www.city.takasago.lg.jp/robots.txt")
    try: rp.read()
    except Exception as e: print("robots.txt取得失敗(許可として扱う):", e)
    if not rp.can_fetch(UA, URL): print("robots.txtで禁止のため停止"); sys.exit(1)
    time.sleep(3)
    req = urllib.request.Request(URL, headers={"User-Agent": UA})
    data = urllib.request.urlopen(req, timeout=60).read()
    open(path, "wb").write(data)
t = open(path, encoding="utf-8", errors="replace").read()
title = re.search(r"<title>(.*?)</title>", t, re.S); h1 = re.search(r"<h1[^>]*>(.*?)</h1>", t, re.S)
def clean(x): return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", x))).strip()
rows = []
for r in re.findall(r"<tr[^>]*>(.*?)</tr>", t, re.S):
    c = [clean(x) for x in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", r, re.S)]
    if c: rows.append(c)
def kanji(s): return set(re.findall(r"[一-鿿々]", unicodedata.normalize("NFKC", s).replace("﨑", "崎")))
out = []; used = set(); notes = []
for c in rows:
    if len(c) < 3 or not re.match(r"^\d+$", c[0].replace(",", "")): continue
    name = c[1]; k = kanji(name)
    nn = unicodedata.normalize("NFKC", name).replace("﨑", "崎").replace(" ", "")
    def score(i, v):
        sk, sy = SURN[i]
        b = len(k & kanji(v)) + (0.5 if re.sub(r"[ぁ-ん]", "", nn) == v else 0)
        if nn.startswith(sk) or nn.startswith(sy): b += 2 + (1 if len(sk) > 1 else 0)
        return b
    sc = sorted(((score(i, v), i) for i, v in ROSTER.items()), reverse=True)
    best = sc[0]; second = sc[1]
    mid = best[1] if best[0] > 0 and best[0] > second[0] and best[1] not in used else ""
    if mid: used.add(mid)
    else: notes.append("名前が決まらない: %s (候補 %s %s / %s %s)" % (name, best[1], ROSTER[best[1]], second[1], ROSTER[second[1]]))
    out.append({"順位": c[0], "選管の表記": name, "議員ID": mid, "議員(名簿)": ROSTER.get(mid, ""), "党派": c[2] if len(c) > 2 else "", "得票数": c[3] if len(c) > 3 else "", "当落": c[4] if len(c) > 4 else "", "出典URL": URL})
with open("raw/analysis/election_2022.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0].keys()) if out else ["順位"]); w.writeheader(); w.writerows(out)
S = ["ページ: %s / %s" % (clean(title.group(1)) if title else "", clean(h1.group(1)) if h1 else ""), "表の行数: %d / 読み取れた候補: %d / 議員IDが決まった: %d / 名簿(19人)で未対応: %s" % (len(rows), len(out), len(used), sorted(set(ROSTER) - used))]
S += notes + [""] + ["%s | %s | %s | %s | %s | %s" % (o["順位"], o["選管の表記"], o["議員(名簿)"], o["党派"], o["得票数"], o["当落"]) for o in out]
upd = re.search(r"(更新日|掲載日)[:：]?\s*([^<\n]{0,30})", clean(t))
S.append("更新日の記載: %s" % (upd.group(0) if upd else "見つからず"))
open("raw/analysis/summary_election_v1.txt", "w", encoding="utf-8").write("\n".join(S))
print("done")
