# Zotero 本地接口速查（zotero-integrated-mcp v1.1.0）

Zotero 桌面开着就有两个口子，**不需要在 WorkBuddy 里挂 MCP 就能直接打**：

| 端口 | 协议 | 用途 |
|---|---|---|
| `http://127.0.0.1:23119/api/users/0/...` | 只读 REST | 查条目、查分类、查附件，快 |
| `http://127.0.0.1:23120/mcp` | MCP streamable-http | 写条目、挂附件、打标签、建分类 |

REST 只读：`DELETE` 返回 **501**，改不动任何东西。

## JSON-RPC 调用骨架

```python
POST http://127.0.0.1:23120/mcp
Content-Type: application/json
Accept: application/json, text/event-stream

{"jsonrpc":"2.0","id":1,"method":"tools/call",
 "params":{"name":"write_item","arguments":{...}}}
```

返回 `result.content[0].text` 是**字符串化的 JSON**，要再 `json.loads` 一次。

## 常用工具

### write_item —— 建条目 / 挂附件 / 换父项

```json
// create
{"action":"create","itemType":"journalArticle",
 "fields":{"title":"...","publicationTitle":"...","date":"1991","volume":"8","issue":"01",
           "pages":"58-64","language":"zh-CN","url":"...","abstractNote":"..."},
 "creators":[{"creatorType":"author","lastName":"郑焕隆"}],
 "tags":["蓝鼎元","潮汕"]}
// → result.data.itemKey

// import（把本地 PDF 挂到条目下）
{"action":"import","filePath":"<PDF 绝对路径，反斜杠>",
 "parentItemKey":"IM7H9CE9","title":"xxx（PDF）"}
// → result.data.attachmentKey

// reparent（把已有独立附件挪到别的条目下）
{"action":"reparent","attachmentKeys":["SE98LADE"],"parentKey":"XXXX"}
```

**`filePath` 必须用反斜杠**。正斜杠 → `OperationError: could not parse path (NS_ERROR_FILE_UNRECOGNIZED_PATH)`。

### 其他

| 工具 | 关键参数 | 说明 |
|---|---|---|
| `create_collection` | `name`, `parentCollection?` | 返回 `key` |
| `get_collections` | `recursive` | 建之前先查同名，别重复建 |
| `add_items_to_collection` | `collectionKey`, `itemKeys[]` | 批量，一次搞定 |
| `remove_items_from_collection` | 同上 | 只摘出分类，不删条目 |
| `delete_collection` | `collectionKey`, `deleteItems:false` | 条目默认保留 |
| `write_metadata` | `itemKey`, `fields`, `creators` | 全量覆盖 creators |
| `write_tag` | **`action`(add/remove/set)**, `itemKey`, `tags` | 漏 `action` 直接报错 |
| `get_item_details` | `itemKey` | 含 `attachments[]`（有 hasFulltext/size/path） |
| `search_library` / `get_collection_items` | 关键词 / key | 查重用 |

**没有 `delete_item`**。误建的条目只能让用户手动丢回收站；本地 API 也删不了。
补救手法：`write_metadata` 改成真实文献复用掉，或打 `重复待删` 标签方便用户批量清。

## 去重的判断顺序

1. 标题归一化（去标点、小写、只留中日韩+字母数字）后完全相同 → 确定重复。
2. 前 12 字相同 → 疑似重复，人工看一眼。
3. 保留哪条：**优先用户原有记录**——它通常 issue 字段更全、PDF 文件名是 Zotero 规范格式
   （`作者 - 年 - 标题.pdf`）、可能已有高亮批注（查 `/items/<attachmentKey>/children` 里的 `annotation`）。
4. 新条目移出分类即可，并给原条目补上本次的主题标签，保持两边一致。

## 常见坑

- `write_tag` 不传 `action` → `KeyError: 'result'`（MCP 返回 error 而非 result）。
- 建条目时 `fields` 里塞 `citationKey` 会残留，清理用 `write_metadata {"citationKey": ""}`。
- 新建条目会自动带 `/unread` 标签（Zotero 7 行为），如需干净用 `write_tag action=set` 覆盖。
- `write_item create` 返回结构不稳定，取值走 `res["data"]["itemKey"]`，并做好 fallback。
