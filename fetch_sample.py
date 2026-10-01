# 高砂市議会 会議録検索システム B3: 前任期(2022年9月10日〜2026年9月9日)の会議日を列挙する
# 本文は取得しない。閲覧画面(年→会議→日)をたどり、会議日の一覧(CSV)を作るだけ。
# 守ること: 1件ごとに5秒空ける / 取得は最大120件 / robots.txtで禁止なら停止 / CAPTCHAがあれば停止
import csv
import datetime
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlencode
from urllib.robotparser import RobotFileParser

BASE = "http://www.kensakusystem.jp/takasago/"
INDEX = BASE + "index.html"
SEE = BASE + "cgi-bin2/See.exe"
ROBOTS = "http://www.kensakusystem.jp/robots.txt"
UA = "takasago-giin-map-research/0.4 (civic data research, low rate)"
WAIT = 5
MAX_REQUESTS = 120
TERM_START = datetime.date(2022, 9, 10)
TERM_END = datetime.date(2026, 9, 9)
YEARS = [4, 5, 6, 7, 8]  # 令和4〜8年
OUT = pathlib.Path("raw")
PAGES = OUT / "b3"
PAGES.mkdir(parents=True, exist_ok=True)
LOG = []
REQUESTS = 0
ERRORS_IN_ROW = 0


def log(msg):
    line = datetime.datetime.utcnow().isoformat() + "Z " + msg
    print(line)
    LOG.append(line)


def finish(code):
    (OUT / "log_b3.txt").write_text("\n".join(LOG) + "\n", encoding="utf-8")
    sys.exit(code)


def decode(data):
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("cp932", errors="replace")


rp = RobotFileParser()
rp.set_url(ROBOTS)
try:
    rp.read()
    log("robots.txt を確認しました")
except Exception as e:
    log("robots.txt の取得に失敗(許可として扱います): " + str(e))


def fetch(url, name, data=None):
    """成功すれば本文(文字列)、失敗すれば None。"""
    global REQUESTS, ERRORS_IN_ROW
    if REQUESTS >= MAX_REQUESTS:
        log("取得件数の上限に達したため停止")
        finish(1)
    if not rp.can_fetch(UA, url):
        log("robots.txt で禁止されているため停止: " + url)
        finish(1)
    REQUESTS += 1
    time.sleep(WAIT)
    headers = {"User-Agent": UA}
    body = None
    if data is not None:
        body = urlencode(data, encoding="cp932").encode("ascii")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        headers["Referer"] = SEE
    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            status = r.status
    except Exception as e:
        ERRORS_IN_ROW += 1
        log("ERROR %s: %s %s" % (e, url, data))
        if ERRORS_IN_ROW >= 3:
            log("3回続けて失敗したため停止")
            finish(1)
        return None
    ERRORS_IN_ROW = 0
    text = decode(raw)
    (PAGES / (name + ".txt")).write_text(text, encoding="utf-8")
    log("OK %s %d bytes -> %s" % (status, len(raw), name))
    if "captcha" in text.lower():
        log("CAPTCHA らしき記述があるため停止")
        finish(1)
    return text


def see(treedepth, name):
    return fetch(SEE, name, data=[("Code", CODE), ("treedepth", treedepth), ("page", ""), ("fileName", "")])


def parse_date(file_name):
    m = re.match(r"^R(\d{2})(\d{2})(\d{2})", file_name)
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return datetime.date(2018 + y, mo, d)
    except ValueError:
        return None


idx = fetch(INDEX, "index")
if idx is None:
    log("トップページが取得できないため停止")
    finish(1)
mc = re.search(r"Code=([A-Za-z0-9]+)", idx)
if not mc:
    log("Code が見つからないため停止")
    finish(1)
CODE = mc.group(1)

rows = []
seen = set()
for y in YEARS:
    year_label = "令和 %d年" % y
    page = see(year_label, "year_R%02d" % y)
    if page is None:
        continue
    values = []
    for v in re.findall(r"treedepth\.value='([^']*)'", page):
        if v.startswith(year_label) and len(v.strip()) > len(year_label) and ("定例会" in v or "臨時会" in v or "委員会" in v):
            if v not in values:
                values.append(v)
    log("%s: 会議の数 %d" % (year_label, len(values)))
    for k, v in enumerate(values, 1):
        mm = re.search(r"(\d+)月(定例会|臨時会)", v)
        kind = "本会議" if mm else "委員会"
        if y == 4 and mm and int(mm.group(1)) < 9:
            continue  # 令和4年の9月より前は前任期の前
        if y == 4 and not mm:
            continue
        sp = see(v, "sess_R%02d_%02d" % (y, k))
        if sp is None:
            continue
        pat = re.compile(r"fileName=([A-Za-z0-9]+)&startPos=0[\"'][^>]*>(.*?)</A>", re.S | re.I)
        n = 0
        for fn, inner in pat.findall(sp):
            label = re.sub(r"<[^>]+>", "", inner)
            label = re.sub(r"\s+", " ", label).strip()
            if fn in seen:
                continue
            seen.add(fn)
            dt = parse_date(fn)
            inside = "Y" if dt and TERM_START <= dt <= TERM_END else "N"
            rows.append([kind, v.strip(), year_label, fn, dt.isoformat() if dt else "", label, inside])
            n += 1
        log("  %s -> 会議日 %d" % (v.strip(), n))

rows.sort(key=lambda r: (r[4], r[3]))
with open(OUT / "meeting_days.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["区分", "会議名", "年", "fileName", "日付", "表示ラベル", "前任期内"])
    w.writerows(rows)

inside = [r for r in rows if r[6] == "Y"]
log("会議日の合計 %d(うち前任期内 %d: 本会議 %d、委員会 %d)" % (
    len(rows), len(inside), sum(1 for r in inside if r[0] == "本会議"), sum(1 for r in inside if r[0] == "委員会")))
log("取得回数 %d" % REQUESTS)
log("完了")
finish(0)
