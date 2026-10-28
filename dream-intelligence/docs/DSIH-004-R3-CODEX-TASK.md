# DSIH-004-R3｜Intelligence Analyzer 正负样本校准

## 0. 工单定位

这是 DSIH Intelligence Analyzer v0.1 的最后一张校准单。

当前已验证：
- 真实 DeepSeek 云 API 可用
- 真实 Raw Item → Analysis → 程序 Priority 链路可用
- 三条普通热点均被正确压低到 Priority 4 / 11 / 7
- Today NULL 时间回归已修复
- 正式数据库当前保持可用

本工单只回答一个问题：

> Analyzer 遇到真正与 Dream Stream 高相关 / 中相关 / 低相关的信息时，是否能形成合理的相对排序？

不开发新功能。

---

# 1. 核心目标

使用真实 DeepSeek Provider，对 **3 条人工构造的隔离校准样本**进行分析：

```text
高相关：AI Video / Dream Stream核心能力
中相关：Agent / Workflow / Browser Automation
低相关：普通社会热点
```

验证结果是否满足最基本的排序关系：

```text
High > Medium > Low
```

只看相对排序，不设死具体分数。

---

# 2. 严格隔离

校准样本不得写入正式：

```text
data/dsih.db
```

不得修改正式：

```text
sources
items
analysis
```

优先方式：

```text
直接调用现有 Analyzer 对内存中的测试 Item 分析
→ 结果只写入报告
```

若现有 Analyzer 必须依赖数据库，可使用临时 SQLite：

```text
tmp / test DB
```

任务结束后删除。

禁止污染正式 81 条 Raw Item 与现有 Analysis。

---

# 3. 三条固定校准样本

以下内容明确标记为：

```text
SYNTHETIC CALIBRATION FIXTURE
```

它们是测试输入，不代表真实新闻，不得写进正式情报库。

## Sample A｜High Relevance

Title:

```text
AI video model adds multi-reference character consistency and controllable action guidance for production workflows
```

Content:

```text
A new AI video generation capability supports multiple reference images for character consistency, stronger action guidance, and workflow integration. These capabilities could directly affect Dream Stream Video Studio's character asset, shot generation, and action-control pipeline.
```

预期方向：

```text
category: AI_VIDEO
Dream Stream relevance: 高
recommended_action: READ 或 WATCH
Priority: 三条中最高
```

不要要求具体分数。

---

## Sample B｜Medium Relevance

Title:

```text
Browser automation framework improves agent task reliability and adds workflow integration hooks
```

Content:

```text
A browser automation framework improves long-running agent reliability and exposes cleaner integration hooks for workflow systems. It is not directly a video-generation capability, but it may become useful infrastructure for Dream Stream agents or future automation modules.
```

预期方向：

```text
category: AI 或 OTHER（均可，只要解释合理）
Dream Stream relevance: 中等
recommended_action: READ / WATCH
Priority: 应低于 A、高于 C
```

---

## Sample C｜Low Relevance

Title:

```text
Local food festival draws large weekend crowds
```

Content:

```text
A local food festival attracted many visitors over the weekend, featuring restaurants, live performances, and family activities. The event has no direct connection to AI, video generation, workflow automation, agents, or Dream Stream.
```

预期方向：

```text
category: OTHER
Dream Stream relevance: 很低
recommended_action: IGNORE
Priority: 三条中最低
```

---

# 4. 使用现有 Analyzer

必须使用当前生产：

```text
dsih-analyzer-v0.1
```

以及当前：

```text
intelligence_profile
priority formula
OpenAI-compatible DeepSeek client
```

禁止为了让测试通过而修改：

```text
Prompt
Profile
Priority Formula
Category list
recommended_action rules
```

本工单是测量，不是调参。

---

# 5. 云 API

继续使用已配置的：

```text
DSIH_LLM_BASE_URL
DSIH_LLM_API_KEY
DSIH_LLM_MODEL
```

不得输出 API Key。

最多允许：

```text
3 次正常分析调用
+
每条最多 1 次现有 JSON 修复重试
```

禁止模型 A/B 测试。

---

# 6. 验收维度

对每条记录：

```text
Category
Summary
Why it matters

Importance
Novelty
Credibility
Personal relevance
Dream Stream relevance
Actionability

Priority
Tags
Recommended action
```

然后验证：

## Ranking

```text
Priority_A > Priority_B > Priority_C
```

以及：

```text
DreamStreamRelevance_A > DreamStreamRelevance_B > DreamStreamRelevance_C
```

如果没有满足：

不要调参。

只记录失败证据，交由人工审核。

---

# 7. 质量底线

额外检查：

### A
高相关样本不能被判：

```text
IGNORE
```

除非模型给出非常明确且合理的理由。

### B
低相关样本不应被判为：

```text
AI_VIDEO
```

### C
模型不得虚构测试输入之外的：

```text
具体公司
发布日期
产品版本
真实发布事件
```

### D
Priority 必须继续由程序计算。

---

# 8. 不允许修改生产代码

理想结果：

```text
Production code modified: NO
```

允许：
- 新建报告
- 临时运行脚本（不提交 / 任务后删除）
- 测试夹具

如果发现必须修改生产代码才能完成校准：

```text
STOP
BLOCKED
```

先报告，不擅自改。

---

# 9. 回归

本工单不需要重新跑全部功能开发，但至少确认：

```text
现有 backend tests PASS
Today API 200
```

不需要重新构建新 UI 功能。

若现有 CI / 命令非常轻量，可继续跑 TypeScript / build，但不得扩大范围。

---

# 10. Stop Rule

满足以下即停止：

```text
3 条真实 DeepSeek 校准完成
+
结果未污染正式 DB
+
相对排序证据已记录
```

无论排序是否理想，都停止。

不要当场调 Prompt。

---

# 11. 验收报告

保存：

```text
docs/DSIH-004-R3-report.md
```

结构：

## A. Isolation
```text
Production DB touched? NO
Temporary DB used:
Production code modified? NO
```

## B. Provider
```text
Base URL:
Model:
API key logged? NO
```

## C. Sample A
```text
Category:
Summary:
Why it matters:
Importance:
Novelty:
Credibility:
Personal relevance:
Dream Stream relevance:
Actionability:
Priority:
Tags:
Recommended action:
```

## D. Sample B
同上。

## E. Sample C
同上。

## F. Ordering Check
```text
Priority A > B > C ? YES/NO
Dream Stream relevance A > B > C ? YES/NO
High sample incorrectly ignored? YES/NO
Low sample misclassified as AI_VIDEO? YES/NO
```

## G. Hallucination Check
```text
Invented company/version/date/release? YES/NO
Notes:
```

## H. Regression
```text
Backend tests:
Today API:
```

## I. Scope Audit
```text
Prompt modified? NO
Profile modified? NO
Priority formula modified? NO
Production DB modified? NO
Today modified? NO
Frontend modified? NO
New framework added? NO
```

## J. Final
只能：

```text
PASS
PASS WITH WARNINGS
BLOCKED
```

---

# 12. 判定原则

Codex 不自行宣布 Analyzer “质量优秀”。

只报告事实。

后续由人工审核决定：

```text
若排序和解释合理
→ 冻结 Analyzer v0.1
→ 进入 DSIH-005 Today Intelligence

若排序明显异常
→ 单独开 Analyzer v0.1.1 调整工单
```
