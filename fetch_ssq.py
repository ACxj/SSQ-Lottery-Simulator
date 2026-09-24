# -*- coding: utf-8 -*-
"""
双色球数据自动更新脚本（供 GitHub Actions / 手动运行）
- 读取仓库根目录的 ssq_data.json
- 调用中国福彩网官方开奖接口（服务端抓取，无跨域限制）
- 有新期则自动合并到数据数组头部并写回
- 无新期则静默退出（不产生提交）

v2：详细错误诊断。失败时打印具体原因（超时/连接/HTTP状态/解析），便于定位。
用法: python fetch_ssq.py
"""
import json
import re
import sys
import urllib.request
import urllib.parse
import urllib.error
import datetime

API = "https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice?" + urllib.parse.urlencode(
    {"name": "ssq", "issueCount": 12})
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.cwl.gov.cn/ygkj/wqkjgg/ssq/",
    "Accept": "application/json, text/javascript, */*; q=0.01",
}


def fetch_rows():
    """返回 result 数组；失败时抛出带原因的异常。"""
    req = urllib.request.Request(API, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            raw = resp.read().decode("utf-8", "replace")
            print("[ok] cwl.gov.cn HTTP %d, %d bytes" % (resp.status, len(raw)))
    except urllib.error.HTTPError as e:
        raise RuntimeError("cwl.gov.cn HTTP %d %s" % (e.code, e.reason))
    except urllib.error.URLError as e:
        raise RuntimeError("cwl.gov.cn 网络错误: %r" % e.reason)
    except Exception as e:
        raise RuntimeError("cwl.gov.cn 未知错误: %r" % e)
    try:
        data = json.loads(raw)
    except Exception as e:
        raise RuntimeError("JSON 解析失败: %r，前200字节=%s" % (e, raw[:200]))
    return data.get("result") or []


def valid_row(r):
    if not r or not r.get("code"):
        return None
    reds = (r.get("red") or "").split(",")
    if len(reds) != 6:
        return None
    try:
        vals = [int(x) for x in reds]
        blue = int(r.get("blue", 0))
    except (TypeError, ValueError):
        return None
    if not all(1 <= v <= 33 for v in vals):
        return None
    if not 1 <= blue <= 16:
        return None
    date = re.sub(r"\s*\(.*?\)\s*", "", str(r.get("date", ""))).strip()
    return [str(r["code"]), date,
            *[str(v).zfill(2) for v in vals], str(blue).zfill(2)]


def main():
    path = "ssq_data.json"
    try:
        with open(path, encoding="utf-8") as f:
            obj = json.load(f)
    except FileNotFoundError:
        obj = {"updated": "", "latest": "", "data": []}
    except Exception as e:
        print("ERROR: 读取 %s 失败: %r" % (path, e))
        sys.exit(1)
    try:
        rows = fetch_rows()
    except RuntimeError as e:
        print("ERROR: %s" % e)
        sys.exit(1)
    existing = {r[0] for r in obj.get("data", [])}
    new_rows = []
    for r in rows:
        row = valid_row(r)
        if row and row[0] not in existing:
            new_rows.append(row)
            existing.add(row[0])
    if not new_rows:
        print("no new draw, latest =", obj.get("latest", ""))
        return
    obj["data"] = new_rows + obj.get("data", [])
    obj["latest"] = obj["data"][0][0]
    obj["updated"] = datetime.datetime.now().strftime("%Y-%m-%d")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    print("updated %d issue(s), latest = %s" % (len(new_rows), obj["latest"]))


if __name__ == "__main__":
    main()
