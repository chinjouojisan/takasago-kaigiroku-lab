# 高砂市議会 会議録検索システムの「調査用」取得スクリプト(B0)
# 目的: 実際のHTML構造を確認するため、少数のページだけを低頻度で保存する。
# 守ること: 1件ごとに数秒空ける / 取得は最大6件 / robots.txtで禁止なら停止 / CAPTCHAがあれば停止
import datetime
import html
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

BASE = "http://www.kensakusystem.jp/takasago/"
INDEX = BASE + "index.html"
ROBOTS = "http://www.kensakusystem.jp/robots.txt"
UA = "takasago-giin-map-research/0.1 (civic data research, low rate)"
WAIT = 5  # 秒
OUT = pathlib.Path("raw")
OUT.mkdir(exist_ok=True)
LOG = []


def log(msg):
    line = datetime.datetime.utcnow().isoformat() + "Z " + msg
    print(line)
    LOG.append(line)


def finish(code):
    (OUT / "log.txt").write_text("\n".join(LOG) + "\n", encoding="utf-8")
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


def get(url, name):
    if not rp.can_fetch(UA, url):
        log("robots.txt で禁止されているため停止: " + url)
        finish(1)
    time.sleep(WAIT)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            data = r.read()
            status = r.status
            ctype = r.headers.get("Content-Type")
    except urllib.error.HTTPError as e:
        log("HTTP %s: %s" % (e.code, url))
        finish(1)
    except Exception as e:
        log("ERROR %s: %s" % (e, url))
        finish(1)
    text = decode(data)
    (OUT / name).write_bytes(data)
    (OUT / (name + ".utf8.txt")).write_text(text, encoding="utf-8")
    log("OK %s %s %d bytes %s -> %s" % (status, ctype, len(data), url, name))
    if "captcha" in text.lower():
        log("CAPTCHA らしき記述があるため停止")
        finish(1)
    return text


def hrefs(text):
    return [html.unescape(h) for h in re.findall(r"""href=["']([^"']+)["']""", text, re.I)]


# 1. トップページ(リンクから Code を含むURLを拾う。値は直接書かない)
idx = get(INDEX, "index.html")
links = hrefs(idx)
see = next((h for h in links if "See.exe" in h), None)
form = next((h for h in links if "Search2.exe" in h and "sTarget=2" in h), None)
topic = next((h for h in links if "KeyWord=PCB" in h), None) or next((h for h in links if "KeyWord=" in h), None)
log("見つかったリンク: 閲覧=%s / 検索画面=%s / トピック=%s" % (bool(see), bool(form), bool(topic)))
if not (see and form and topic):
    log("必要なリンクが見つからないため停止")
    finish(1)

# 2. 閲覧トップ、検索画面、トピック検索の結果
see_html = get(urljoin(INDEX, see), "see_top.html")
(OUT / "see_top_links.txt").write_text("\n".join(hrefs(see_html)), encoding="utf-8")
get(urljoin(INDEX, form), "search_form.html")
res_html = get(urljoin(INDEX, topic), "search_topic.html")
res_links = hrefs(res_html)
(OUT / "search_topic_links.txt").write_text("\n".join(res_links), encoding="utf-8")

# 3. 検索結果から日別ページへのリンクを1件だけ取得
day = next((h for h in res_links if "See.exe" in h and "&" in h), None)
if day:
    get(urljoin(INDEX, day), "day_sample.html")
else:
    log("日別ページへのリンクが見つかりませんでした(検索結果の構造は raw/search_topic.html で確認)")
log("完了")
finish(0)
