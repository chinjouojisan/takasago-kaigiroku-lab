# 高砂市議会 会議録検索システム B4: 本会議の会議日ごとに、発言の索引と本文テキストを取得する
# 入力: raw/meeting_days.csv(B3で作成)。出力: raw/index/<fileName>.csv、raw/minutes/<fileName>.txt、raw/b4_status.csv
# 守ること: 1件ごとに5秒空ける / 1回の実行は最大50日 / robots.txtで禁止なら停止 / CAPTCHAがあれば停止
#          3回続けて失敗したら停止 / 取得済みの日は飛ばす(何回か実行すれば続きから進む)
import csv
import datetime
import html as htmllib
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlencode, urljoin
from urllib.robotparser import RobotFileParser

BASE = "http://www.kensakusystem.jp/takasago/"
INDEX = BASE + "index.html"
CGI = BASE + "cgi-bin2/"
ROBOTS = "http://www.kensakusystem.jp/robots.txt"
UA = "takasago-giin-map-research/0.5 (civic data research, low rate)"
WAIT = 5
MAX_DAYS = 50
MAX_REQUESTS = 175
PROBE = ["R080318B01"]  # 委員会の形式を確認するための1日(令和8年3月18日 総務常任委員会)
OUT = pathlib.Path("raw")
MIN = OUT / "minutes"
IDX = OUT / "index"
DBG = OUT / "b4debug"
for p in (MIN, IDX, DBG):
    p.mkdir(parents=True, exist_ok=True)
LOG = []
REQUESTS = 0
ERRORS_IN_ROW = 0
DEBUG_SAVED = 0


def log(msg):
    line = datetime.datetime.utcnow().isoformat() + "Z " + msg
    print(line)
    LOG.append(line)


def finish(code):
    (OUT / "log_b4.txt").write_text("\n".join(LOG) + "\n", encoding="utf-8")
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


def request(url, data=None, debug_name=None):
    """成功すれば本文(文字列)、失敗すれば None。"""
    global REQUESTS, ERRORS_IN_ROW
    if REQUESTS >= MAX_REQUESTS:
        log("取得件数の上限に達したため、ここで終了します")
        finish(0)
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
        headers["Referer"] = INDEX
    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            raw = r.read()
    except Exception as e:
        ERRORS_IN_ROW += 1
        log("ERROR %s: %s" % (e, url))
        if ERRORS_IN_ROW >= 3:
            log("3回続けて失敗したため停止")
            finish(1)
        return None
    ERRORS_IN_ROW = 0
    text = decode(raw)
    if debug_name:
        (DBG / debug_name).write_text(text, encoding="utf-8")
    if "captcha" in text.lower():
        log("CAPTCHA らしき記述があるため停止")
        finish(1)
    return text


def strip_tags(s):
    s = re.sub(r"<[^>]+>", "", s)
    return htmllib.unescape(s).strip()


def parse_speakers(page):
    """発言者の一覧ページから、発言ごとの (No, 位置番号, ページ, 発言者表記, 冒頭) を取り出す。"""
    cbs = list(re.finditer(r"""name=["']?downloadPos["']?\s+value=["']?(\d+)["']?""", page, re.I))
    rows = []
    cur_page = ""
    for i, m in enumerate(cbs):
        end = cbs[i + 1].start() if i + 1 < len(cbs) else len(page)
        before = page[max(0, m.start() - 100):m.start()]
        mn = re.findall(r"No\.(\d+)", before)
        seg = page[m.end():end]
        pg = re.search(r">\s*P\.(\d+)\s*<", seg)
        if pg:
            cur_page = pg.group(1)
        lab = re.search(r"r_TextFrame\.exe[^\"']*[\"'][^>]*>\s*<font[^>]*>([^<]*)<", seg, re.I)
        first = re.search(r"""id=["']span\d+["'][^>]*>(.*?)</div>""", seg, re.S | re.I)
        rows.append([
            mn[-1] if mn else "",
            m.group(1),
            pg.group(1) if pg else "",
            cur_page,
            htmllib.unescape(lab.group(1)).strip() if lab else "",
            re.sub(r"\s+", " ", strip_tags(first.group(1)))[:40] if first else "",
        ])
    return rows


def count_speeches(text):
    return len(re.findall(r"^○", text, re.M))


def download(code, fn, positions):
    def post(chunk):
        data = [("Code", code), ("fileName", fn)] + [("downloadPos", p) for p in chunk]
        return request(CGI + "GetPerson.exe", data=data)

    text = post(positions)
    if text is not None and count_speeches(text) >= 0.7 * len(positions):
        return text
    log("  まとめての取得が不十分なため、60件ずつに分けます: %s" % fn)
    parts = []
    for i in range(0, len(positions), 60):
        t = post(positions[i:i + 60])
        if t is None:
            return None
        if i > 0:
            k = t.find("\n\n")
            t = t[k + 2:] if k >= 0 else t
        parts.append(t.rstrip("\n"))
    return "\n\n".join(parts) + "\n"


def process_day(code, fn, meta):
    global DEBUG_SAVED
    dbg = DEBUG_SAVED < 2
    frame = request(CGI + "ResultFrame.exe?Code=%s&fileName=%s&startPos=0" % (code, fn),
                    debug_name=("%s_frame.html" % fn) if dbg else None)
    if frame is None:
        return False
    m = re.search(r"""<FRAME[^>]+SRC=["']([^"']*r_Speakers\.exe[^"']*)["']""", frame, re.I)
    if not m:
        log("  %s: 発言者一覧のフレームが見つかりません" % fn)
        (DBG / ("%s_frame_nofound.html" % fn)).write_text(frame, encoding="utf-8")
        return False
    page = request(urljoin(CGI, m.group(1)), debug_name=("%s_speakers.html" % fn) if dbg else None)
    if page is None:
        return False
    if dbg:
        DEBUG_SAVED += 1
    rows = parse_speakers(page)
    if not rows:
        log("  %s: 発言の位置番号が1件も取れません" % fn)
        return False
    with open(IDX / (fn + ".csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["fileName", "No", "位置番号", "ページ(表示行のみ)", "ページ(繰越)", "発言者表記", "冒頭"])
        for r in rows:
            w.writerow([fn] + r)
    text = download(code, fn, [r[1] for r in rows])
    if text is None:
        return False
    (MIN / (fn + ".txt")).write_text(text, encoding="utf-8")
    status_path = OUT / "b4_status.csv"
    new = not status_path.exists()
    with open(status_path, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["fileName", "日付", "会議名", "発言数(一覧)", "「○」の発言数(本文)", "本文の文字数", "取得日時"])
        w.writerow([fn, meta[0], meta[1], len(rows), count_speeches(text), len(text), datetime.datetime.utcnow().isoformat() + "Z"])
    log("  %s: 一覧 %d件 / 本文 %d発言 / %d文字" % (fn, len(rows), count_speeches(text), len(text)))
    return True


# 会議日の一覧(B3)を読む
days = []
with open(OUT / "meeting_days.csv", encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if r["区分"] == "本会議" and r["前任期内"] == "Y":
            days.append((r["日付"], r["fileName"], r["会議名"]))
days.sort()
todo = [d for d in days if not (MIN / (d[1] + ".txt")).exists()]
log("本会議の会議日 %d日、取得済み %d日、未取得 %d日" % (len(days), len(days) - len(todo), len(todo)))

idx = request(INDEX)
if idx is None:
    log("トップページが取得できないため停止")
    finish(1)
mc = re.search(r"Code=([A-Za-z0-9]+)", idx)
if not mc:
    log("Code が見つからないため停止")
    finish(1)
CODE = mc.group(1)

# 委員会の形式の確認(1日だけ)
for fn in PROBE:
    if not (MIN / (fn + ".txt")).exists():
        log("確認用(委員会): %s" % fn)
        process_day(CODE, fn, ("2026-03-18", "令和 8年 総務常任委員会(確認用)"))

done = 0
for date, fn, name in todo:
    if done >= MAX_DAYS:
        break
    log("取得: %s %s" % (date, name))
    if process_day(CODE, fn, (date, name)):
        done += 1

remaining = len([d for d in days if not (MIN / (d[1] + ".txt")).exists()])
log("今回の取得 %d日 / 取得回数 %d / 本会議の未取得 %d日(残りがあれば、もう一度実行すると続きから進みます)" % (done, REQUESTS, remaining))
log("完了")
finish(0)
