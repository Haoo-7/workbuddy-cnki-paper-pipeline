# workbuddy-cnki-paper-pipeline

把"某个研究主题的中文文献"从知网检索一路做到 Zotero 和 ima 两个库里都能直接读全文。
适合写文献综述前的一次性搜集：一次跑完，产出可核对的分组清单。

## 它解决什么

检索本身不难，难在这条链路上的三处断点，每一步都能让人卡半天：

| 断点 | 现象 | 本 Skill 的处理 |
|---|---|---|
| 下载被劫持 | 点下载没反应，目录里没有文件，报 `USER_CANCELED` | 定位到下载管理器扩展，给出一句话处置；固定从详情页 `#pdfDown` 取 PDF 而非结果列表的"下载" |
| 题录散落 | 卷、期、页码只在详情页一行题录里；多作者在详情页被粘成一串 | 固定提取脚本与正则，作者以结果列表为准 |
| 入库不可回滚 | 媒体 ID 绑定知识库，传错库报 `220030`；两边都没有删除接口 | 把"确认目标库"写进开工前置检查；Zotero 侧做重跑保护 |

## 安装

把 `workbuddy-cnki-paper-pipeline/` 整个目录放进宿主的 Skill 目录即可，例如：

```text
~/.workbuddy/skills/workbuddy-cnki-paper-pipeline/
```

无需 `pip install`，脚本只用 Python 3.10+ 标准库。

## 依赖

| 组件 | 用途 | 是否必须 |
|---|---|---|
| Python 3.10+ | 跑脚本 | 必须 |
| Zotero 7 + zotero-integrated-mcp 插件 | 建条目、挂 PDF、归分类 | 必须 |
| 能驱动登录态浏览器的 CLI（本文验证的是 `bsk`） | 检索与下载 | 必须 |
| ima 知识库连接器 | 第五阶段入库 | 可选，缺省降级为手动上传 |

零配置、零密钥。脚本不读环境变量里的令牌，也不写任何凭据文件；
对象存储的上传凭证由运行时临时签发，只在内存里存活。

## 使用

在对话里说清三件事就够了：

```text
研究主题 + 检索词 / 目标 Zotero 分类 / 目标 ima 知识库
```

之后交给 Agent。它会在动手前自检环境，按阶段跑并报告验证点，最后给出
`results_all.json`、`merged.json`、`文献清单.md` 和 PDF 目录路径。

想手动跑某一步：

```bash
python scripts/zotero_mcp.py --check                        # 环境自检
python scripts/dedup_check.py --collection KEY --items merged.json
python scripts/push_zotero.py  --items merged.json --collection KEY --tags 主题词
python scripts/ima_put.py      --creds creds.json --dir ./pdf
```

`push_zotero.py` 默认带重跑保护：分类里已有同名条目会跳过，重复执行不会产生副本；
确实要新建副本时加 `--force`。

## 兼容范围

- **已验证**：Windows + Edge + Zotero 7 + Python 3.13，完整跑通一次 20 篇的批量入库。
- **未实测**：macOS / Linux、其它浏览器 CLI。操作序列本身是通用的，
  差异集中在 `references/cnki-browser.md` 的命令部分。
- **宿主依赖**：ima 段需要宿主提供 ima MCP 连接器。没有连接器时，
  前四个阶段（检索、下载、题录、Zotero）照常可用，ima 段降级为交付 PDF 让用户手动拖入。
- 仅覆盖中文知网；英文数据库不在范围内。

## 数据边界

- 不绕过付费墙，不导出 cookie 或访问令牌，不代替用户购买。
- PDF 只从用户自己已授权的机构入口获取，也只写进用户自己的文库。
- 脚本不上传、不联网回传任何本地内容；对象存储写入只指向 ima 签发的目标路径。

## 输出

| 文件 | 内容 |
|---|---|
| `results_all.json` | 冻结的检索结果，含站内序号与详情页链接，可复现 |
| `merged.json` | 合并题录，字段见 `references/cnki-browser.md` |
| `文献清单.md` | 分组表格 + 检索式 + 命中数 + 入库位置 + 未完成项 |
| `zotero_keys.json` | 新建条目 key 与逐条处理状态 |

## 说明

本 Skill 的 frontmatter 只使用通用字段（`name` / `description` / `license` / `compatibility` / `metadata`），
可以直接被按 agent-plugins 规范校验的宿主加载。

若你的宿主（例如 WorkBuddy）要求技能声明 `agent_created: true` 才能由 Agent 侧编辑或删除，
在 `SKILL.md` 的 frontmatter 里加一行即可，不影响任何脚本与流程。

## License

MIT
