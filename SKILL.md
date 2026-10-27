---
name: workbuddy-cnki-paper-pipeline
description: |
  批量把知网文献从检索做到双库入库：检索并冻结结果、按相关度选题、逐篇下载并校验 PDF、
  从详情页抓题录、与既有 Zotero 分类比对去重，最后建 Zotero 条目挂附件、把同一批 PDF
  灌进 ima 知识库，并产出可核对的分组文献清单。
  当用户要求"帮我下知网论文并放进 Zotero / ima""把这个主题的中文文献收一批"
  "先攒一版文献综述的料"时使用。
  不要用于：单篇论文的引用格式转换、查某篇论文讲了什么（走检索类 Skill）、
  只检索不入库的问答、英文数据库（Web of Science、JSTOR 等）。
  与 cnki-skills 分工：那边负责检索与题录导出，本 Skill 负责下载校验、去重和双库落盘。
license: MIT
compatibility: |
  核心流程（知网检索、PDF 下载、题录抓取、Zotero 入库）依赖浏览器 CLI 与 Zotero 本地 HTTP 接口，
  与宿主无关。ima 入库段依赖宿主提供 ima MCP 连接器（本 Skill 在 WorkBuddy 的 ima 连接器上验证过）；
  没有该连接器时走"手动上传"降级路径，见"宿主适配"。
  脚本只用 Python 3.10+ 标准库。已验证 Windows + Edge + Zotero 7；
  macOS/Linux 与其它浏览器未实测。
metadata:
  version: "1.1.0"
---

# 知网 → Zotero / ima 文献流水线

把"某个主题的中文文献"从检索一路推到"两个库里都能直接读全文"。
难点不在检索，而在这条链路上的三处断点：下载被下载管理器劫持、题录字段散落在详情页、
入库接口有不可回滚的绑定关系。本 Skill 把这些固化成脚本与检查点。

## 何时使用

用户给出研究主题并要求"下载论文 + 入库"，或已有一批知网结果需要批量落盘。
不适合单篇引用转换、纯检索问答、英文数据库。

## 前置检查（先查再动，缺一即停）

| 依赖 | 检查 | 缺失处置 |
|---|---|---|
| 浏览器 CLI | `bsk --version`；`bsk browsers` 有已登录知网的实例 | 报告缺失，不自行安装 |
| Zotero 桌面在运行 | `python scripts/zotero_mcp.py --check` | 请用户打开 Zotero |
| Zotero MCP 插件 | 同上，检查 23120 端口 | 提示装 zotero-integrated-mcp |
| ima 连接器 | 工具清单里有 `mcp__ima-mcp__*` | 走"宿主适配"的降级路径 |
| 下载管理器 | 首次下载报 `USER_CANCELED` 即怀疑 IDM | **请用户关掉 IDM 扩展** |

**开工前必须问清三件事**（其余信息自己查，不要反复追问）：

1. 检索词与字段（默认主题）。
2. 目标 Zotero 分类——**用既有分类**，不要另建顶层分类。
3. 目标 ima 知识库——让用户从列表里点全名。库里真名和口语简称常差几个字，
   而 **传错库不可回滚**。

## 主流程

### 阶段 1：检索并冻结结果

按 `references/cnki-browser.md` 起会话、进国内站、检索、翻页、抓表，落成 `results_all.json`。

**验证点**：记录检索式、排序方式、抓取时间，以及按详情页 `href` 去重后的条数。
分页会整段重复，未去重就报总数会虚高。

### 阶段 2：选题与下载

按与研究问题的相关度分组挑选，不要机械全下。命中一两百条时选 15–25 篇：
围绕用户问题的"核心机制"多收，外围主题少收，并在交付时说明取舍。

下载用详情页 `#pdfDown`，落盘后逐文件校验 `%PDF-` 头。
目录 `~/Downloads/CNKI/YYYY-MM-DD/`，文件名 `序号_篇名_第一作者.pdf`。

**验证点**：每个文件都有 `%PDF-` 前缀且体积非零；队列文件末尾带换行
（否则 `while read` 会静默漏掉最后一行）。

### 阶段 3：抓题录

同一批链接再走一遍详情页，取 `.author` / `#ChDivSummary` / `.keywords` / `.top-tip`，
合并成 `merged.json`，字段与正则见 `references/cnki-browser.md`。

**验证点**：逐条打印作者、卷期页、摘要长度；缺失字段留空，不要编。

### 阶段 4：Zotero 入库

```bash
python scripts/dedup_check.py --collection <KEY> --items merged.json
python scripts/push_zotero.py  --items merged.json --collection <KEY> --tags 主题词1,主题词2
```

`push_zotero.py` 内置重跑保护：已在目标分类里的标题自动跳过，重复执行不会灌进第二批副本。

**验证点**：分类条目数 = 原有 + 新增 − 跳过；抽查 `get_item_details` 能看到
`attachments[].hasFulltext = true`。

### 阶段 5：ima 入库

三步不可省：`create_media`（MCP）→ 签名 PUT 到对象存储（脚本）→ `add_knowledge`（MCP）。

```bash
python scripts/ima_put.py --creds creds.json --dir <PDF 目录>
```

**验证点**：`get_knowledge_list` 的 `knowledge_total_size` 增量等于本批篇数；
`media_state=1` 表示仍在解析，不要提前宣布可问答。

## 宿主适配

| 环节 | 依赖 | 换宿主时怎么办 |
|---|---|---|
| 检索 / 下载 | 浏览器 CLI + 已登录知网 | 换任意能驱动登录态浏览器的工具，操作序列见 `references/cnki-browser.md` |
| 题录 | 同上 | 无需改 |
| Zotero | 本地 23119/23120 HTTP | 与宿主无关，任何语言都能直接打 |
| ima | 宿主的 ima MCP 连接器 | 无连接器时降级为"手动上传"：交付 PDF + `文献清单.md`，让用户在 ima 客户端自行拖入 |

ima 段"媒体 ID 绑定知识库、凭据一次一用"属于服务端约束，换宿主也不变。

## 三条硬约束

1. **媒体 ID 绑定知识库**。A 库创建的媒体拿去 B 库添加会报 `220030 权限不足`，
   换库必须重新 `create_media`。目标库要在开工时定死。
2. **两边都没有删除接口**。Zotero 本地 API 的 `DELETE` 返回 501；ima 也没有删除/移动工具。
   传错库、建错条目只能人工清理，因此宁可多确认一次。
3. **Zotero 挂附件的 `filePath` 必须用反斜杠 Windows 路径**，正斜杠报
   `NS_ERROR_FILE_UNRECOGNIZED_PATH`。脚本已用 `win_path()` 处理。

## 资源导航

| 文件 | 何时读 |
|---|---|
| `references/cnki-browser.md` | 阶段 1–3：命令、DOM 选择器、提取 JS、下载与 IDM 坑、题录正则 |
| `references/zotero-mcp.md` | 阶段 4：接口速查、去重判断顺序、常见报错 |
| `references/ima-mcp.md` | 阶段 5：三步走、知识库类型、凭据与绑定约束 |
| `scripts/zotero_mcp.py` | Zotero 客户端（MCP + 只读 REST），可作库复用 |
| `scripts/dedup_check.py` | 只读比对，出重复报告 |
| `scripts/push_zotero.py` | 建条目、挂 PDF、入分类，含重跑保护 |
| `scripts/cos_put.py` | 对象存储临时密钥签名 PUT |
| `scripts/ima_put.py` | 按凭据批量上传 |

## 完成标准

- 每个阶段都跑过验证点，失败项如实列出（未下载条数、待清重复、ima 未解析篇数）。
- 交付：`results_all.json`、`merged.json`、`文献清单.md`、PDF 目录绝对路径。
- 检索式或筛选标准若被改动，必须显式说明；不得用"更权威"的论文静默替换命中列表条目。

## 边界

- 不绕过付费墙、不导出 cookie/token、不代用户购买。
- 摘要 ≠ 全文；程序校验 ≠ 学术结论正确。
- 不替用户决定研究框架，取舍理由要摆出来让人判断。
