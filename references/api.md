# Local app API

Default base: `http://127.0.0.1:8765`. Verify GET `/api/status` has `application: bili-summary`. Use JSON request bodies; HTTP errors contain `message`. Do not start a second server sharing the same data directory.

POST `/api/jobs`:

```json
{"kind":"prompt","prompt":"帮我总结抖音最近稍后再看的3条视频","auto_skip":true}
```

Alternatively `{"kind":"links","links":["https://www.douyin.com/video/ID"],"auto_skip":true}` or `{"kind":"watch_later","platform":"douyin","limit":3,"auto_skip":true}`. The platform for Bilibili is `bilibili`. Read the returned batch and poll GET `/api/batches` every few seconds. Terminal item states: done, skipped, failed, canceled. Do not resubmit while queued/running.

GET `/api/items/{id}` returns full item including summary and transcript. Read `summary.one_line`, `points`, `highlights`, `audience`, `skip_note`; skipped items have `skip_reason`, failed items have `error`. Report those honestly. POST `/api/items/{id}/retry` or `/cancel` performs the respective action only when needed. GET `/api/library` lists completed and skipped entries.
