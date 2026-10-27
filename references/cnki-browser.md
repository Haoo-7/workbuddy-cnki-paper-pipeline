# 知网 + bsk 浏览器操作要点（实测于 2026-10）

## 起会话

```bash
bsk --version
BSK_AUTO_START=0 bsk daemon start --foreground   # 必须 run_in_background=true
BSK_AUTO_START=0 bsk status --json               # 另起一次调用验证
BSK_AUTO_START=0 bsk browsers                    # 拿 instance_id
BSK_AUTO_START=0 bsk session start --json --browser <instance_id>
```

收尾**必须** `bsk session stop <session_id>`。

## 入口与登录

- 国内站入口：`https://kns.cnki.net/kns8s/defaultresult/index`（直接进，不要走 www.cnki.net，可能被劫到 oversea）。
- 页面标题含 `检索-中国知网`、header 出现机构名（如"暨南大学"）即为机构 IP 已识别。
- 检索项默认 `主题`；切到 `学术期刊` 会把检索重跑一遍，比在结果里筛更省事。

## 检索与抓表

输入框填词后 `bsk press Enter --ref <ref>`。结果表结构与提取 JS：

```js
// 每页行
(()=>{const rows=[...document.querySelectorAll("table.result-table-list tbody tr")];
return rows.map((tr,i)=>{const a=tr.querySelector("td.name a");
const tds=[...tr.querySelectorAll("td")].map(td=>td.innerText.trim().replace(/\s+/g," "));
return {i:i+1,title:a?a.innerText.trim():"",href:a?a.getAttribute("href"):"",cells:tds};});})()
```

`cells` 依次大致为：站内序号、标题、作者（`;` 分隔）、出处、日期、被引、下载、操作。

翻页：`div.pages a[data-curpage="2"]`，点完 `sleep 3` 再抓。
**分页会有整段重复**（第 3 页可能重复第 2 页的内容），按 `href` 去重。

## 详情页题录

```js
(()=>{const g=s=>{const e=document.querySelector(s);return e?e.innerText.trim().replace(/\s+/g," "):""};
return {title:document.title.replace(/\s*-\s*中国知网\s*$/,""),authors:g(".author"),
tip:g(".top-tip"),abstract:g("#ChDivSummary"),keywords:g(".keywords")};})()
```

- `.top-tip` 示例：`汕头大学学报 . 1991 (01) : 58-64`，正则：
  `^(?P<src>.+?)\s*\.\s*(?P<year>\d{4})\s*(?:,\s*(?P<vol>\d+))?\s*(?:\((?P<iss>[^)]*)\))?\s*(?::\s*(?P<pg>[0-9\-–—+]+))?`
- 末尾 `查看该刊数据库收录来源` 要去掉。
- `h1` 可能命中隐藏的"自动登录"，标题取 `document.title` 更稳。

## 下载（最容易翻车的一段）

1. 结果列表的"下载"**不保证 PDF**（可能给 .caj）。必须在详情页用 **PDF 下载**。
2. 控件：`#pdfDown`（同页还有 `#cajDown`，两者 href 同为 `bar.cnki.net/bar/download/order?id=...`）。
3. 正确姿势：`bsk download "#pdfDown" --out "<绝对路径>.pdf" --session <id>`。
4. **不要**把 `bar.cnki.net` 的地址直接 `bsk navigate` —— 报 `来源应用不正确(01)`，它校验 Referer，必须从详情页点击触发。
5. 页面内 `fetch()` 也拿不到：跨域被 CORS 拦。

### IDM 抢下载

症状：`bsk download` 返回 `error: ... USER_CANCELED`，Downloads 目录零文件，Edge 扩展目录里能找到
`ngpampappnmepgilojfohadhhmbhlaek`（IDM Integration Module）。
处置：请用户到 `edge://extensions` 关掉 IDM 开关，或退出 IDM。**关掉后同样的命令立刻成功**（749KB PDF 一次过）。

### 校验

```python
open(f,'rb').read(5) == b'%PDF-'
```
扩展名不算验证；`application/pdf` 的 CAJ 或错误页存成 .pdf 都算失败。

### 命名

`序号_篇名_第一作者.pdf`，剔除 `\ / : * ? " < > |`。序号沿用站内序号，方便和清单对账。
下载队列用 TSV + bash while read 时，**文件末尾必须有换行**，否则最后一行被静默跳过（本次漏了 1 篇）。
