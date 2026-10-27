# ima 知识库入库要点

服务端：`https://ima.qq.com/mcp`（streamable-http，OAuth 由 WorkBuddy 连接器托管）。
**无法用脚本直连**——只能通过 `mcp__ima-mcp__*` 工具调用，所以上传要拆成"工具调用 + 本地脚本"两段。

## 三步走

```
create_media(knowledge_base_id, file_name, file_size, content_type, file_ext)
   → { media_id, cos_credential{token, secret_id, secret_key, start_time, expired_time,
                                bucket_name, region, cos_key} }
PUT https://{bucket}.cos.{region}.myqcloud.com/{cos_key}   ← 本地脚本，见 scripts/cos_put.py
add_knowledge(knowledge_base_id, media_id)
```

## 硬约束

1. **media_id 与知识库绑定**。A 库 create 的 media 拿去 B 库 add → `code:220030 权限不足`。
   换库必须重新 `create_media`（连 cos_key 前缀都会变：`5/<空间hash>/file_manager/xxx.pdf`）。
   → **开工前确认目标库 id**，选错库 = 全量重传。
2. **凭据一次一用**。用上一批的 secret/token 去传新 cos_key → `403 Forbidden`。
   每条 create_media 的凭据只能配它自己的 cos_key，有效期约 12 小时（`expired_time - start_time = 43200`）。
3. **没有删除/移动接口**。传错库只能让用户在 ima 客户端手动删。
   → 目标库确认这一步不能省。
4. `create_media` 要传**精确 MIME**（pdf → `application/pdf`），禁用 `application/octet-stream` 兜底；
   `file_size` 必须和实际字节数一致，服务端会校验。

## 找知识库

```python
mcp__ima-mcp__get_knowledge_base_list({"params":[{"limit":50,"type":"KBT_MINE_KB"}]})
```
type 取值：`KBT_MINE_KB`（个人库）/ `KBT_SHARED_KB`（共享库）/ `KBT_SUBSCRIBED_JOIN_KB`（我加入的）
/ `KBT_SUBSCRIBED_CREATE_KB`。**`KBT_UNUSE` 会报参数校验失败，别用。**

课程/团队用的库通常是 `KBT_SHARED_KB`（type=1002），个人笔记库才是 `KBT_MINE_KB`（type=1001）。
用户口语简称和库里真名经常差几个字（"明清潮汕开化研究" ↔「教化与重塑：明清时期潮汕地区"开化"研究」），
**按关键词搜出来报全名给用户确认**，别凭感觉选。

## 入库后

- `get_knowledge_list({knowledge_base_id, limit})` 校验条数（看 `knowledge_total_size`）。
- `media_state`：1=待解析，2=解析完成；`parse_progress` 0→100。PDF 解析要几分钟，别急着报完工。
- `fetch_media_content` 取全文；`search_knowledge` 做库内语义检索。

## 成本提示

每次 create_media 的返回里 `cos_credential.token` 有 1.3KB 左右，20 个文件就是 26KB 的上下文开销。
批量时按 5 个一组：并行 create_media → 一次写成一个 JSON → 跑一次 ima_put.py → 并行 add_knowledge。
