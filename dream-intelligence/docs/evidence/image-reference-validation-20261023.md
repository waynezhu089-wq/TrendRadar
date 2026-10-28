# 图片参考素材第一版 — 2026-10-23

## 已实现范围

同一方案助手/研究工作台支持“资讯研究”和“图片参考素材”。图片方案只接入 Openverse。自然语言输入题材和用途后，助手生成待确认草案；确认后用户手动运行。每次最多2个检索词、12张候选。图片以宽松双列卡片展示，窄屏单列；保留原站、作者、许可、署名、尺寸。按元数据给推荐理由与用途建议，支持跨运行收藏及用户点选下载。模型未查看图片像素，不宣称视觉识别或已核验许可。

音频和图书文件收集未实现；豆瓣书影评论仍是已有文字研究功能。没有新增调度或通知任务。

## 真实验证

- Openverse 公开检索接口 HTTP 200；Wikimedia API 本机返回403，未继续排查或绕过。
- 独立验收输入：“为奇幻短片的场景设计寻找雾中森林参考图，优先横图，保留作者和许可信息”。
- 应用真实模型返回 `collection_type=images`、Openverse 来源、话题与目的草案。
- 在 `data/image-validation-20261023T060041.db` 运行正常图片流程，状态 COMPLETED：收到4张、推荐4张、入库4张、错误0。
- 图片总结明确说明仅依标题/标签/尺寸筛选、未查看像素；横向判断仅来自宽高，画面和许可待用户核对。
- 独立验收库：research_images=4，items=0，analysis=0，notification_deliveries=0；未创建日常用户方案。
- 抽查2张预览响应均 HTTP 200、Content-Type=image/jpeg。
- 真实文件下载次数0。下载的大小、签名、私有地址重定向、缓存复用与错误清理用隔离测试验证；未将其标为真实下载验收通过。

## 数据保留与测试隔离

旧库迁移产生自动备份 `data/dsih.db.pre-dsih-007-20261023T055746276276.bak`。发现旧 Daily 测试启动 TestClient 时会触发真实应用初始化，导致此轮迁移早于计划重载时机执行；已修复该测试夹具，使其不再初始化开发库。没有用测试样本写入日常数据库。

迁移后逐表比较备份与当前库的全部原有字段，均一致：research_plans 3、research_runs 13、sources 11、items 14605、analysis 310、notification_deliveries 17。迁移备份连接现已显式关闭，修复 Windows 文件占用；重复迁移测试不再生成额外备份。

## 检查结果

- 后端193项通过；前端22项通过；TypeScript与Vite构建通过。
- 覆盖同源ID去重、不伪造图像分析、模型异常保留候选、错误不泄露响应、旧分析失败保留、跨运行收藏、下载限制、旧库幂等升级。
- 只重载已核实的本地API进程，重载前无RUNNING研究；未重启或修改 Scheduler、Watchdog、飞书。
- 更新后health、today、daily-brief、research-plans、OpenAPI及前端settings均HTTP200；图片模式与下载接口已加载，原3个方案仍为research。
- 浏览器页面点击、视觉体验和真实下载尚待用户验收，不标记为USER_UX_PASS。

## 主要文件

后端：`app/research/images.py`、`app/db/models.py`、`app/db/database.py`、`app/schemas/research.py`、`app/api/v1/research.py`、`app/api/v1/daily.py`、`app/research/plan_assistant.py`、`app/api/v1/plan_assistant.py`。

前端：`src/pages/ImageResults.tsx`、`src/pages/Research.tsx`、`src/pages/PlanAssistant.tsx`、`src/api/research.ts`、`src/style.css`。另有对应测试、显式独立验收脚本和Git忽略规则。

参考：[Openverse官方API说明](https://api.openverse.org/v1/)。

DeepSeek MCP：本次未使用。真实模型调用来自应用现有模型API。
