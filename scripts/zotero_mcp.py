"""Zotero 本地接口小工具：MCP(JSON-RPC over HTTP) + 只读 REST API。

Zotero 桌面运行时自带两个端口：
  23119  /api/users/0/...   只读 REST（查条目、查分类，快）
  23120  /mcp               zotero-integrated-mcp 插件（写条目、挂附件、打标签）

无需 WorkBuddy 挂载 MCP，直接用 urllib 打这两个端口即可。
"""

import json
import urllib.error
import urllib.parse
import urllib.request

MCP_URL = "http://127.0.0.1:23120/mcp"
REST_BASE = "http://127.0.0.1:23119/api/users/0"


def call(name, args, url=MCP_URL, timeout=180):
    """调用 Zotero MCP 工具，返回已解析的 JSON。"""
    payload = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
         "params": {"name": name, "arguments": args}}
    ).encode()
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json, text/event-stream")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.load(resp)
    if "error" in body:
        raise RuntimeError("MCP error: %s" % body["error"])
    text = body["result"]["content"][0]["text"]
    try:
        return json.loads(text)
    except ValueError:
        return text


def rest(path, base=REST_BASE, timeout=30):
    """GET 只读 REST，path 形如 /collections/KEY/items/top?limit=100"""
    with urllib.request.urlopen(base + path, timeout=timeout) as resp:
        return json.load(resp)


def collection_items(key, base=REST_BASE, page=100):
    """取分类下全部顶层条目（自动翻页）。"""
    out, start = [], 0
    while True:
        chunk = rest("/collections/%s/items/top?limit=%d&start=%d" % (key, page, start), base)
        out.extend(chunk)
        if len(chunk) < page:
            return out
        start += page


def is_alive():
    try:
        rest("/items?limit=1")
        return True
    except (urllib.error.URLError, OSError):
        return False


def mcp_alive(url=MCP_URL):
    """探测 23120/mcp：tools/list 能返回工具清单即视为可用。

    注意 zotero-integrated-mcp 的 tools/list 响应里没有 serverInfo，
    只能看 result.tools。tools/call 的返回则是 result.content[0].text。
    """
    try:
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}).encode()
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json, text/event-stream")
        with urllib.request.urlopen(req, timeout=15) as resp:
            tools = json.load(resp).get("result", {}).get("tools") or []
        return any(t.get("name") == "write_item" for t in tools)
    except (urllib.error.URLError, OSError, ValueError):
        return False


def win_path(p):
    """Zotero 的 import 动作只认反斜杠 Windows 路径。"""
    return str(p).replace("/", "\\")


def _cli():
    """自检入口：python scripts/zotero_mcp.py --check

    分别在两行报告只读 REST（23119）与 MCP 写接口（23120）是否可用，
    任一不可用返回退出码 1，便于在流水线前置检查里直接调用。
    """
    import argparse
    ap = argparse.ArgumentParser(description="Zotero 本地接口自检")
    ap.add_argument("--check", action="store_true", help="检查 REST 与 MCP 两个端口")
    ap.add_argument("--mcp", default=MCP_URL)
    ap.add_argument("--rest", default=REST_BASE)
    a = ap.parse_args()
    if not a.check:
        ap.print_help()
        return 0
    rest_ok = False
    try:
        rest("/items?limit=1", base=a.rest)
        rest_ok = True
    except (urllib.error.URLError, OSError):
        pass
    mcp_ok = mcp_alive(a.mcp)
    print("REST 23119 (read-only) : %s" % ("OK" if rest_ok else "FAIL"))
    print("MCP  23120 (write)     : %s" % ("OK" if mcp_ok else "FAIL"))
    if not rest_ok:
        print("→ 打开 Zotero 桌面后重试；本地 API 随 Zotero 启动。")
    if not mcp_ok:
        print("→ 安装/启用 zotero-integrated-mcp 插件后重试。")
    return 0 if (rest_ok and mcp_ok) else 1


if __name__ == "__main__":
    raise SystemExit(_cli())
