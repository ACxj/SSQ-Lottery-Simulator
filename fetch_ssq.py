# -*- coding: utf-8 -*-
"""
双色球数据自动更新脚本（供 GitHub Actions / 手动运行）
- 读取仓库根目录的 ssq_data.json
- 调用中国福彩网官方开奖接口（服务端抓取，无跨域限制）
- 有新期则自动合并到数据数组头部并写回
- 无新期则静默退出（不产生提交）
用法: python fetch_ssq.py
"""
import json
import re
import urllib.request
import urllib.parse
import datetime

API = "https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice?" + urllib.parse.urlencode(
    {"name": "ssq", "issueCount": 12})
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.cwl.gov.cn/ygkj/wqkjgg/ssq/",
    "Accept": "application/json, text/javascript, */*; q=0.01",
}


def fetch_rows():
    req = urllib.request.Request(API, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
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
    date = re.sub(r"\s*\(.*?\)\s*", "", str(r.get("date", ""))).strip()  # 去掉"(二)"星期后缀
    return [str(r["code"]), date,
            *[str(v).zfill(2) for v in vals], str(blue).zfill(2)]


def main():
    path = "ssq_data.json"
    try:
        with open(path, encoding="utf-8") as f:
            obj = json.load(f)
    except FileNotFoundError:
        # 仓库还没有数据文件：用抓到的最近一期初始化（至少要 100 期才可用，提示人工补全）
        obj = {"updated": "", "latest": "", "data": []}
    existing = {r[0] for r in obj.get("data", [])}
    new_rows = []
    for r in fetch_rows():
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
