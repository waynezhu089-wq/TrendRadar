# MediaCrawler 本机差异归档

原机第三方工具位于 `.lab-tools/MediaCrawler-main`，主体源码不随 DSIH 复制。与原下载包逐文件比较，代码/配置仅存在本目录补丁所记录的两处文件差异：

- `config/base_config.py`：关闭 CDP、关闭连接已有浏览器、条数限制 3、关闭评论采集；没有认证字符串改动。
- `media_platform/bilibili/core.py`：将搜索结果限制到 3 条再读取详情。

补丁：`mediacrawler-dsih-local.patch`；上游原许可原样保留于 `MediaCrawler-LICENSE.txt`。不要把第三方补丁视为 DSIH 自有或任意可再许可代码。

原下载包 `MediaCrawler-main.zip` 的 SHA256：

`762eb46175511bcd67e48c10483ba3729876142c7b517f2a57b7464d13ae8dda`

在独立安装的对应版本 MediaCrawler 根目录先执行 `git apply --check <本补丁绝对路径>`，确认版本上下文匹配后再 `git apply <本补丁绝对路径>`。若不匹配，停止核对版本，不盲目替换源码。DSIH 的 B 站适配器本身也显式设置范围与限额，见 `backend/app/research/bilibili.py`。

补丁不包含登录态、Cookies、缓存、下载输出、浏览器文件、虚拟环境或秘密配置。新机仍需要独立安装依赖与亲自登录。归档时只检查补丁与原机差异相符，没有在第二台主机或另一个 MediaCrawler 版本执行真实采集验收。
