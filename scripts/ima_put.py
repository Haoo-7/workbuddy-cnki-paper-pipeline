"""批量把本地 PDF 上传到 ima 知识库对应的 COS 位置。

ima 入库三步走：create_media → COS PUT → add_knowledge。
本脚本负责第 2 步（第 1、3 步是 MCP 工具调用，脚本代劳不了）。

用法：
    python ima_put.py --creds creds.json [--dir PDF目录] [--content-type application/pdf]

creds.json 形如（每条就是 create_media 的返回，外加一个 file 字段：
file 可以是绝对路径，也可以是相对 --dir 的文件名）：
[
  {"file": "03_蓝鼎元年表_林世杰.pdf",
   "media_id": "pdf_xxx_yyy",
   "cos_credential": {"token": "...", "secret_id": "...", "secret_key": "...",
                      "start_time": "...", "expired_time": "...",
                      "bucket_name": "...", "region": "...", "cos_key": "..."}}
]

输出：
    逐条 OK/FAIL + 结尾汇总；--out 写 {"ok":[{file,media_id,...}], "fail":[...]}
    每个 media_id 记得随后交给 mcp__ima-mcp__add_knowledge。
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cos_put import upload


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--creds", required=True)
    ap.add_argument("--dir", default="", help="file 为相对路径时的基准目录")
    ap.add_argument("--content-type", default="application/pdf")
    ap.add_argument("--out", default="ima_media_ids.json")
    a = ap.parse_args()

    jobs = json.load(open(a.creds, encoding="utf-8"))
    ok, fail = [], []
    for j in jobs:
        path = j["file"]
        if a.dir and not os.path.isabs(path):
            path = os.path.join(a.dir, path)
        if not os.path.exists(path):
            print("FAIL 文件不存在 %s" % path, flush=True)
            fail.append({"file": j["file"], "reason": "file-not-found"})
            continue
        cred = j.get("cos_credential", j)
        try:
            code = upload(cred, path, a.content_type)
            print("OK   %s %s" % (code, j["file"]), flush=True)
            ok.append({"file": j["file"], "media_id": j.get("media_id"),
                       "kb": j.get("knowledge_base_id")})
        except Exception as exc:  # noqa: BLE001
            print("FAIL %s %s" % (j["file"], repr(exc)[:160]), flush=True)
            fail.append({"file": j["file"], "reason": repr(exc)[:160]})

    print("\n成功 %d / %d" % (len(ok), len(jobs)))
    if fail:
        print("失败清单：%s" % json.dumps(fail, ensure_ascii=False))
        print("常见原因：凭据已过期（约 12 小时）、cos_key 属于别的知识库、文件被占用。")
    json.dump({"ok": ok, "fail": fail}, open(a.out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("下一步：把上面每个 media_id 逐个调用 mcp__ima-mcp__add_knowledge（knowledge_base_id 必须与创建时一致）。")


if __name__ == "__main__":
    main()
