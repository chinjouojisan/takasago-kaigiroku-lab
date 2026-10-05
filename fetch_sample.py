# B13: 高砂市の「市議会だより(テキスト版)」16号分(前任期の定例会ごと)を取得して保存する
# 出力: raw/dayori/<ID>.html(原本), raw/dayori/<ID>.txt(本文を表の形を保って文字にしたもの), raw/dayori/status.csv, raw/dayori/log_b13.txt
# 守ること: 1件ごとに5秒空ける / robots.txtで禁止なら停止 / 3回続けて失敗したら停止 / 取得済みは飛ばす
import csv, datetime, pathlib, re, sys, time, urllib.request, urllib.error
from html.parser import HTMLParser
from urllib.robotparser import RobotFileParser

BASE = "https://www.city.takasago.lg.jp/soshikikarasagasu/gikaijimukyoku/takasagoshigikai/2/"
ISSUES = [  # (ID, 定例会, パス)
    ("D01", "令和4年9月定例会", "reiwa4/8294.html"),
    ("D02", "令和4年12月定例会", "reiwa4/8522.html"),
    ("D03", "令和5年3月定例会", "reiwa5/9012.html"),
    ("D04", "令和5年6月定例会", "reiwa5/9303.html"),
    ("D05", "令和5年9月定例会", "reiwa5/9646.html"),
    ("D06", "令和5年12月定例会", "reiwa5/10028.html"),
    ("D07", "令和6年3月定例会", "reiwa6/11097.html"),
    ("D08", "令和6年6月定例会", "reiwa6/11439.html"),
    ("D09", "令和6年9月定例会", "reiwa6/11599.html"),
    ("D10", "令和6年12月定例会", "reiwa6/12385.html"),
    ("D11", "令和7年3月定例会", "reiwa6_1/12432.html"),
    ("D12", "令和7年6月定例会", "reiwa6_1/12623.html"),
    ("D13", "令和7年9月定例会", "reiwa6_1/13005.html"),
    ("D14", "令和7年12月定例会", "reiwa6_1/13745.html"),
    ("D15", "令和8年3月定例会", "reiwa8/13902.html"),
    ("D16", "令和8年6月定例会", "reiwa8/14106.html"),
]
UA = "takasago-giin-map-research/0.5 (civic data research, low rate)"
WAIT = 5
OUT = pathlib.Path("raw/dayori"); OUT.mkdir(parents=True, exist_ok=True)
LOG = []
def log(m):
    line = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") + " " + m
    print(line, flush=True); LOG.append(line)

class T(HTMLParser):
    """表は、セルをタブ、行を改行で区切って文字にする。"""
    BLOCK = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "tr", "table", "section", "ul", "ol", "dt", "dd"}
    def __init__(self):
        super().__init__(); self.o = []; self.skip = 0
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"): self.skip += 1
        if tag in self.BLOCK: self.o.append("\n")
    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"): self.skip = max(0, self.skip - 1)
        if tag in ("td", "th"): self.o.append("\t")
        if tag in self.BLOCK: self.o.append("\n")
    def handle_data(self, d):
        if not self.skip: self.o.append(d)

def to_text(html):
    p = T(); p.feed(html)
    t = "".join(p.o).replace("\xa0", " ")
    t = re.sub(r"[ 　]+\t", "\t", t)
    t = re.sub(r"\n\s*\n+", "\n", t)
    return t.strip() + "\n"

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read()
    for enc in ("utf-8", "cp932"):
        try: return raw.decode(enc)
        except UnicodeDecodeError: pass
    return raw.decode("utf-8", errors="replace")

def main():
    rp = RobotFileParser("https://www.city.takasago.lg.jp/robots.txt")
    try:
        rp.read(); log("robots.txt を確認しました")
    except Exception as e:
        log("robots.txt の取得に失敗(許可として扱います): %r" % e)
    st = OUT / "status.csv"
    rows = {}
    if st.exists():
        for r in csv.DictReader(open(st, encoding="utf-8-sig", newline="")): rows[r["ID"]] = r
    errs = 0
    for i, (iid, name, path) in enumerate(ISSUES):
        url = BASE + path
        if (OUT / (iid + ".txt")).exists():
            log("%s 取得済みのため飛ばします" % iid); continue
        if not rp.can_fetch(UA, url):
            log("robots.txt で禁止されているため停止: " + url); break
        try:
            h = get(url)
            (OUT / (iid + ".html")).write_text(h, encoding="utf-8")
            t = to_text(h)
            (OUT / (iid + ".txt")).write_text(t, encoding="utf-8")
            rows[iid] = {"ID": iid, "定例会": name, "URL": url, "HTMLバイト": str(len(h.encode("utf-8"))), "本文の文字数": str(len(t)),
                         "賛否": str(t.count("賛否")), "○": str(t.count("○")), "×": str(t.count("×")), "表(タブ)行数": str(sum(1 for l in t.split("\n") if "\t" in l)),
                         "取得日時": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
            log("%s %s 取得 %s文字" % (iid, name, len(t))); errs = 0
        except Exception as e:
            errs += 1; log("%s 失敗: %r" % (iid, e))
            if errs >= 3: log("3回続けて失敗したため停止"); break
        if i < len(ISSUES) - 1: time.sleep(WAIT)
    cols = ["ID", "定例会", "URL", "HTMLバイト", "本文の文字数", "賛否", "○", "×", "表(タブ)行数", "取得日時"]
    with open(st, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader()
        for k in sorted(rows): w.writerow(rows[k])
    log("取得済み %d / %d" % (len(rows), len(ISSUES)))
    (OUT / "log_b13.txt").write_text("\n".join(LOG) + "\n", encoding="utf-8")
    # 確認用の短い要約(新しい名前のファイル)
    s = ["生成 " + datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")]
    for k in sorted(rows):
        r = rows[k]; s.append("%s %s 文字%s 賛否%s ○%s ×%s 表行%s" % (k, r["定例会"], r["本文の文字数"], r["賛否"], r["○"], r["×"], r["表(タブ)行数"]))
    (OUT / "summary_dayori_status.txt").write_text("\n".join(s) + "\n", encoding="utf-8")
main()
