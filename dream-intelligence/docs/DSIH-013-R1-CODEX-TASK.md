# DSIH-013-R1｜Announcement Light Read v0.1 — 易读则读，困难则跳过

## 0. 工单定位

项目：Dream Stream Intelligence Hub（DSIH / Radar）  
阶段：Phase E / Market Watch  
优先级：P0

前置已验收：
- DSIH-013：深交所官方公告发现链路 PASS
- 当前 `market_announcements` 已保存可立克最近 10 条官方公告元数据与官方 PDF 链接

本工单采用新的 1.0 原则：

> **没有技术难度的公告正文就读取；有明显技术难度的就跳过，并保留官方链接提醒用户自己查看。**

不为了少数难处理 PDF 引入 OCR、视觉模型或复杂版面分析。

---

# 1. 本工单唯一目标

对现有官方公告做轻量处理：

```text
官方公告元数据
→ 尝试普通 PDF 文本提取
→ 成功：保存正文文本
→ 失败/扫描件/乱码/受保护：跳过正文
→ 无论是否提取成功，都保留官方链接
```

---

# 2. 只处理官方公告

只允许处理：

```text
szse.cn
*.szse.cn
```

尤其：

```text
disc.static.szse.cn
```

第三方 URL：
- 不下载；
- 不处理；
- 记录 warning。

---

# 3. 不做 OCR

明确禁止：

```text
OCR
视觉模型
图片转文字
版面重建
表格识别
复杂 PDF 修复
密码破解
浏览器自动化
```

若普通 PDF 文本提取失败：

```text
直接跳过
```

用户仍可点击官方链接自行查看。

---

# 4. 数据模型

新增独立表：

```text
market_announcement_documents
```

建议最小字段：

```text
id
announcement_id
status
text
char_count
extractor
error_code
created_at
updated_at
```

约束：

```text
UNIQUE(announcement_id)
```

status 只允许：

```text
READABLE
SKIPPED_COMPLEX
FAILED
```

语义：

```text
READABLE
= 普通文本层提取成功，正文可用

SKIPPED_COMPLEX
= 扫描件、无文本层、乱码严重、受保护等；
  1.0 不继续处理

FAILED
= 网络/下载/解析异常，属于可重试的普通失败
```

不要把 PDF 二进制存进 SQLite。

---

# 5. 提取策略

使用成熟轻量 PDF 文本库。

优先：

```text
pypdf
```

或项目已有等价轻量依赖。

流程：

```text
GET 官方 PDF
→ 校验 Content-Type / URL
→ 普通文本提取
→ 合并页面文字
→ 基础清理空白
```

不要做复杂段落重排。

---

# 6. 可读性判定

第一版采用简单规则即可。

例如：

```text
提取文本 strip 后 >= 300 字符
且不是明显空白/乱码
→ READABLE
```

若：

```text
提取为空
文本极少
绝大多数为不可读控制字符
解析器明确提示加密/无文本
```

则：

```text
SKIPPED_COMPLEX
```

不要为了让它“通过”继续升级处理技术。

---

# 7. 首轮真实验收范围

只处理现有可立克公告中的：

```text
最近 3 条
```

每条最多：

```text
1 次正常下载/解析
```

不批量处理全部 10 条。

---

# 8. CLI

新增：

```bash
python -m app.commands.read_market_announcements --latest 3
```

输出：

```text
announcement_id
title
status
char_count
error_code
```

第二次执行：

```text
已存在 READABLE / SKIPPED_COMPLEX
→ SKIP
```

不要重复下载。

---

# 9. Market API

扩展现有：

```http
GET /api/v1/market
```

每条 announcement 增加：

```json
{
  "read_status": "READABLE",
  "text_available": true
}
```

若跳过：

```json
{
  "read_status": "SKIPPED_COMPLEX",
  "text_available": false
}
```

不要把完整正文塞进 `/api/v1/market`。

---

# 10. 正文读取 API

只在 READABLE 时允许：

```http
GET /api/v1/market/announcements/{id}/text
```

返回：

```json
{
  "id": 1,
  "title": "...",
  "text": "..."
}
```

若：

```text
SKIPPED_COMPLEX
```

返回：

```text
409 / 422
```

并明确：

```text
text unavailable; use official URL
```

---

# 11. Frontend

现有 `/market` 公告区域做最小增强：

### READABLE

显示：

```text
[读取正文] [查看官方公告]
```

点击“读取正文”：

```text
展开简单纯文本
```

不要做富文本排版。

### SKIPPED_COMPLEX

显示：

```text
正文未自动读取
[查看官方公告]
```

不要显示错误堆栈。

---

# 12. 阅读状态提醒

新增轻量“已读 / 未读”状态时，优先复用公告表或新增最小字段。

如果为了 `read_by_user` 需要明显重构：

```text
本工单先不做
```

至少页面需要明确：

```text
新公告
```

并保留：

```text
查看官方公告
```

真正的“用户已读状态”可单独下一工单完成。

---

# 13. 数据库边界

允许新增：

```text
market_announcement_documents
```

禁止修改：

```text
sources
items
analysis
feedback
intelligence watchlist
market_watchlist
market_snapshots
market_announcements 原有字段内容
```

---

# 14. 不调用 LLM

严格：

```text
LLM calls = 0
```

不得：

```text
AI 摘要
利好/利空判断
公告分类
投资建议
```

---

# 15. 不接 Scheduler

本工单：

```text
Scheduler modified? NO
```

只做显式 CLI 读取。

等真实效果稳定后再决定是否自动处理新公告。

---

# 16. 自动测试

至少新增：

```text
official PDF download allowed
third-party URL rejected
text PDF -> READABLE
empty/scanned-like PDF -> SKIPPED_COMPLEX
encrypted/unreadable PDF -> SKIPPED_COMPLEX
network failure -> FAILED
second run skips existing terminal statuses
text endpoint returns readable text
text endpoint rejects unavailable text
market API returns read_status
existing announcement metadata unchanged
```

测试使用 fixture PDF / fake HTTP。

不得依赖真实网络。

---

# 17. 真实验收

只处理：

```text
可立克最近 3 条深交所公告
```

报告每条：

```text
title
official_url
status
char_count
extractor
error_code
```

允许结果：

```text
READABLE
SKIPPED_COMPLEX
FAILED
```

核心原则：

> **不要为了把所有 3 条都读出来而升级技术。**

---

# 18. Stop Rule

满足：

```text
最近 3 条完成轻量尝试
+
可读 PDF 正文成功保存
+
难处理 PDF 被安全跳过
+
官方链接始终保留
+
无 OCR / 无 LLM
+
Market API 200
+
页面可以读取正文或跳转官方链接
+
既有数据不变
+
测试通过
```

立即停止。

---

# 19. 验收报告

保存：

```text
docs/DSIH-013-R1-report.md
```

## A. Extractor

```text
library:
OCR used? NO
LLM used? NO
```

## B. Real 3 Documents

逐条：

```text
announcement_id:
title:
url:
status:
char_count:
error_code:
```

## C. API

```text
market API:
text endpoint:
unavailable behavior:
```

## D. Frontend

```text
READABLE action:
SKIPPED action:
official link:
```

## E. Database

```text
existing tables changed? NO
market_announcement_documents before/after:
```

## F. Tests

```text
Backend:
TypeScript:
Frontend build:
```

## G. Scope Audit

```text
OCR added? NO
LLM called? NO
Scheduler modified? NO
Announcement metadata modified? NO
Trading logic added? NO
```

## H. Final

只能：

```text
PASS
PASS WITH WARNINGS
BLOCKED
```

---

# 20. 核心原则

第一版不追求“所有公告都自动读懂”。

只做：

> **容易读取的就读；难处理的就跳过，让用户点击官方原文。**
