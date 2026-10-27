"""把 merged.json 推进 Zotero：建条目 → 挂 PDF → 归入分类。

用法：
    python push_zotero.py --items merged.json --collection QNNTBIM4 \
        [--tags 蓝鼎元,潮汕] [--skip 3,15] [--pre-keyed pk.json] [--item-type journalArticle]

参数：
    --skip       逗号分隔的 num 列表，跳过（通常是 dedup_check 报出的重复项）
    --pre-keyed  JSON {"num": "已有条目key"}，对这些 num 改为更新元数据而非新建
                 （用于复用误建的条目，避免库里多一条孤儿）

输出 zotero_keys.json：{"keys":[...], "report":[...]}，供后续加分类/校验用。
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zotero_mcp as Z


def build_fields(it):
    f = {
        "title": it["title"],
        "publicationTitle": it.get("source", ""),
        "date": str(it.get("year", "")),
        "language": "zh-CN",
    }
    if it.get("href"):
        f["url"] = it["href"]
    for src, dst in (("volume", "volume"), ("issue", "issue"), ("pages", "pages"),
                     ("abstract", "abstractNote")):
        v = it.get(src)
        if v:
            f[dst] = str(v)
    return f


def norm(title):
    t = (title or "").lower()
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]", "", t)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", required=True)
    ap.add_argument("--collection", required=True)
    ap.add_argument("--tags", default="")
    ap.add_argument("--skip", default="")
    ap.add_argument("--pre-keyed", default="")
    ap.add_argument("--item-type", default="journalArticle")
    ap.add_argument("--mcp", default=Z.MCP_URL)
    ap.add_argument("--rest", default=Z.REST_BASE)
    ap.add_argument("--force", action="store_true",
                    help="关掉重跑保护：即使分类里已有同名条目也新建（会产生副本）")
    ap.add_argument("--out", default="zotero_keys.json")
    a = ap.parse_args()

    if not Z.mcp_alive(a.mcp):
        sys.exit("Zotero MCP 不可用（23120/mcp）。确认 Zotero 已开且装了 zotero-integrated-mcp。")

    items = json.load(open(a.items, encoding="utf-8"))
    skip = {int(x) for x in a.skip.split(",") if x.strip()}
    pre = {int(k): v for k, v in json.load(open(a.pre_keyed, encoding="utf-8")).items()} if a.pre_keyed else {}
    tags = [t.strip() for t in a.tags.split(",") if t.strip()]

    # 重跑保护：分类里已有同名条目就跳过，避免重复执行灌进第二批副本
    existing = set()
    if not a.force:
        try:
            existing = {norm(x["data"].get("title", "")) for x in Z.collection_items(a.collection, base=a.rest)}
        except Exception as exc:  # noqa: BLE001
            print("警告：读不到目标分类（%s），重跑保护失效，请确认 key 正确。" % repr(exc)[:80])

    keys, report = [], []
    for it in items:
        num = int(it.get("num", 0))
        if num in skip:
            report.append((num, "skip-dup", ""))
            print("%-4s SKIP (重复)" % num, flush=True)
            continue
        if norm(it.get("title", "")) in existing:
            report.append((num, "skip-exists", ""))
            print("%-4s SKIP (分类里已有同名条目)" % num, flush=True)
            continue

        fields = build_fields(it)
        creators = [{"creatorType": "author", "lastName": x} for x in it.get("authors", []) if x.strip()]
        it_tags = list(tags)
        for kw in (it.get("keywords") or "").split(";"):
            kw = kw.strip()
            if kw and kw not in it_tags:
                it_tags.append(kw)
        it_tags = it_tags[:8]

        key = pre.get(num)
        if key:
            Z.call("write_metadata", {"itemKey": key, "fields": fields, "creators": creators}, a.mcp)
            if it_tags:
                Z.call("write_tag", {"action": "add", "itemKey": key, "tags": it_tags}, a.mcp)
        else:
            res = Z.call("write_item", {"action": "create", "itemType": a.item_type,
                                        "fields": fields, "creators": creators, "tags": it_tags}, a.mcp)
            key = (res.get("data") or {}).get("itemKey") if isinstance(res, dict) else None
            if not key:
                report.append((num, "create-fail", str(res)[:120]))
                print("%-4s CREATE FAIL %s" % (num, str(res)[:160]), flush=True)
                continue

        pdf = it.get("file", "")
        if pdf and os.path.exists(pdf):
            r = Z.call("write_item", {"action": "import", "filePath": Z.win_path(pdf),
                                      "parentItemKey": key,
                                      "title": it["title"] + "（PDF）"}, a.mcp)
            ok = bool(r.get("success")) if isinstance(r, dict) else False
        else:
            ok = False
        keys.append(key)
        report.append((num, key, "pdf-ok" if ok else "pdf-missing"))
        print("%-4s %s pdf:%s" % (num, key, "ok" if ok else "缺失/失败"), flush=True)

    if keys:
        r = Z.call("add_items_to_collection", {"collectionKey": a.collection, "itemKeys": keys}, a.mcp)
        print("\n加入分类：%s" % json.dumps(r, ensure_ascii=False)[:200])

    json.dump({"keys": keys, "report": report}, open(a.out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("共处理 %d 条，key 清单写入 %s" % (len(keys), a.out))


if __name__ == "__main__":
    main()
