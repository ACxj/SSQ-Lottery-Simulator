# -*- coding: utf-8 -*-
"""
双色球数据自动更新脚本（供 GitHub Actions / 手动运行）
- 读取仓库根目录的 ssq_data.json
- 双数据源容错：主源=中国福彩网官方接口；备用源=500.com 历史接口
- 有新期则自动合并到数据数组头部并写回；无新期则静默退出（不产生提交）

v3：cwl 失败（如境外 403）时自动切换 500.com 备用源。
用法: python fetch_ssq.py
"""
import json
import re
import sys
import urllib.request
import urllib.parse
import urllib.error
import datetime

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

CWL_API = "https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice?" + urllib.parse.urlencode(
    {"name": "ssq", "issueCount": 12})
CWL_HEADERS = {
    "User-Agent": UA,
    "Referer": "https://www.cwl.gov.cn/ygkj/wqkjgg/ssq/",
    "Accept": "application/json, text/javascript, */*; q=0.01",
}
W500_URL = "https://datachart.500.com/ssq/history/newinc/history.php?limit=12"


def fetch_cwl():
    """主源：中国福彩网官方接口 → list[['期号','日期',红1..红6,蓝]]"""
    req = urllib.request.Request(CWL_API, headers=CWL_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            raw = resp.read().decode("utf-8", "replace")
            print("[cwl] HTTP %d, %d bytes" % (resp.status, len(raw)))
    except urllib.error.HTTPError as e:
        raise RuntimeError("cwl.gov.cn HTTP %d %s" % (e.code, e.reason))
    except urllib.error.URLError as e:
        raise RuntimeError("cwl.gov.cn 网络错误: %r" % e.reason)
    data = json.loads(raw)
    rows = []
    for r in data.get("result") or []:
        row = norm_cwl(r)
        if row:
            rows.append(row)
    return rows


def norm_cwl(r):
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
    if not all(1 <= v <= 33 for v in vals) or not 1 <= blue <= 16:
        return None
    date = re.sub(r"\s*\(.*?\)\s*", "", str(r.get("date", ""))).strip()
    return [str(r["code"]), date,
            *[str(v).zfill(2) for v in vals], str(blue).zfill(2)]


def fetch_500():
    """备用源：500.com 历史接口 → 同样格式；失败抛 RuntimeError"""
    req = urllib.request.Request(W500_URL, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            raw = resp.read().decode("gbk", "replace")
            print("[500] HTTP %d, %d bytes" % (resp.status, len(raw)))
    except urllib.error.HTTPError as e:
        raise RuntimeError("500.com HTTP %d %s" % (e.code, e.reason))
    except urllib.error.URLError as e:
        raise RuntimeError("500.com 网络错误: %r" % e.reason)
    rows = []
    for tr in re.findall(r'<tr class="t_tr1">(.*?)</tr>', raw, re.S):
        tds = [re.sub(r"<[^>]+>", "", t).strip()
               for t in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if len(tds) < 10:
            continue
        issue = tds[1].strip()
        if re.fullmatch(r"\d{5}", issue):          # 26110 -> 2026110
            issue = "20" + issue
        reds = tds[2:8]
        blue = tds[8]
        date = tds[-1].strip()
        try:
            vals = [int(x) for x in reds]
            b = int(blue)
        except (TypeError, ValueError):
            continue
        if not all(1 <= v <= 33 for v in vals) or not 1 <= b <= 16:
            continue
        if not re.fullmatch(r"\d{7}", issue):
            continue
        rows.append([issue, date,
                     *[str(v).zfill(2) for v in vals], str(b).zfill(2)])
    if not rows:
        raise RuntimeError("500.com 页面解析无有效数据")
    return rows


def fetch_any():
    """主源优先，失败切备用源"""
    try:
        rows = fetch_cwl()
        print("[fetch] 主源成功, %d 期" % len(rows))
        return rows
    except RuntimeError as e:
        print("[fetch] 主源失败: %s，尝试备用源…" % e)
    rows = fetch_500()
    print("[fetch] 备用源成功, %d 期" % len(rows))
    return rows


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
        rows = fetch_any()
    except RuntimeError as e:
        print("ERROR: 所有数据源均失败: %s" % e)
        sys.exit(1)
    existing = {r[0] for r in obj.get("data", [])}
    new_rows = []
    for r in rows:
        if r[0] not in existing:
            new_rows.append(r)
            existing.add(r[0])
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
