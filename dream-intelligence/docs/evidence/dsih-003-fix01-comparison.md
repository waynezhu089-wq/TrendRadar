# Request comparison before modification

| Field | TrendRadar reference | DSIH before |
|---|---|---|
| Method | GET | GET |
| URL | configurable /api/s | configurable /api/s |
| Query | id + bare latest | id only; preserves configured query |
| User-Agent | ordinary Chrome/Windows browser style | DSIH/0.1 |
| Accept | application/json, text/plain, */* | application/json |
| Accept-Language | zh-CN,zh;q=0.9,en;q=0.8 | absent |
| Cache-Control | no-cache | absent |
| Connection | keep-alive | urllib-managed close |
| Timeout | 10 seconds | 20 seconds |
| Redirects | requests default follow | urllib default follow |
| Proxy | optional explicit proxy; library environment defaults | urllib environment/system defaults |

Only inspected reference fetcher read-only. No reference module copied. Plan: ordinary headers, bare latest and 10-second timeout; retain urllib, default redirects and proxy behavior. No retry loop added. This comparison does not establish the cause of 403.
