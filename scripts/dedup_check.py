"""比对 merged.json 与目标 Zotero 分类里的既有条目，报重复。

用法：
    python dedup_check.py --collection QNNTBIM4 --items merged.json [--near 12] [--out dedup.json]

输出：
    控制台分组报告 + --out 指定的 JSON（{dups:[{num,new_title,existing_key,existing_title,match}]}）

只读，不修改任何数据。
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zotero_mcp as Z


def norm(title):
    t = (title or "").lower()
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]", "", t)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--collection", required=True, help="目标分类 key（8 位）")
    ap.add_argument("--items", required=True, help="merged.json")
    ap.add_argument("--near", type=int, default=12, help="判近似的前缀字数，0 表示只查完全相同")
    ap.add_argument("--api", default=Z.REST_BASE)
    ap.add_argument("--out", default="dedup.json")
    a = ap.parse_args()

    if not Z.is_alive():
        sys.exit("Zotero 未运行（23119 无响应）。先让用户打开 Zotero。")

    new_items = json.load(open(a.items, encoding="utf-8"))
    existing = Z.collection_items(a.collection, base=a.api)
    ex_rows = []
    for it in existing:
        d = it.get("data", {})
        ex_rows.append((it["key"], d.get("title", ""), d.get("publicationTitle", ""), d.get("date", "")))

    print("分类内既有条目：%d   待检查新条目：%d" % (len(ex_rows), len(new_items)))
    print("（本脚本应在 push_zotero 之前跑；若这批已经在库里，会把它们自己全报成重复）\n")

    ex_exact, ex_near = {}, {}
    for key, title, src, date in ex_rows:
        ex_exact.setdefault(norm(title), []).append((key, title, src, date))
        if a.near:
            ex_near.setdefault(norm(title)[: a.near], []).append((key, title, src, date))

    dups = []
    for it in new_items:
        n = norm(it["title"])
        hit = ex_exact.get(n)
        match = "exact"
        if not hit and a.near:
            hit = ex_near.get(n[: a.near])
            match = "near"
        if hit:
            key, title, src, date = hit[0]
            dups.append({"num": it.get("num"), "new_title": it["title"], "existing_key": key,
                         "existing_title": title, "existing_source": src,
                         "existing_date": date, "match": match})

    if not dups:
        print("没有发现重复。可以放心入库。")
    else:
        print("发现 %d 条重复（建议保留既有条目，新技术条目移出分类）：\n" % len(dups))
        for d in dups:
            print("  [%s] #%s %s" % (d["match"], d["num"], d["new_title"]))
            print("        既有：%s | %s | %s  (%s)" % (d["existing_key"], d["existing_source"],
                                                      d["existing_date"], d["existing_title"]))
        print("\n保留依据：既有条目通常字段更全、PDF 文件名更规范、可能已有批注。")
        print("处理：push_zotero.py 跳过这些 num，并把它们移出分类（或打 tag 待删）。")

    json.dump({"dups": dups}, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n报告已写入 %s" % a.out)


if __name__ == "__main__":
    main()
