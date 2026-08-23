# 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| 早期日期价格为负 | 复权计算 + 多次分红导致 | 后复权存储下不应出现；若 `factor<1` 或价格为负，取数层已自动整条置 NaN，重下该段即可 |
| `fetch_day_kline` 返回 None | 日期范围 >1500 条 | 使用分段下载或 [`download_day_kline`](download.md) |
| `min_kline_to_qlib` 返回 False | 缺少日历文件 | 先生成 `qlib_data/calendars/{freq}.txt`（`generate_min_calendar`） |
| 北交所 920xxx 股票目录错误 | 旧版未支持 920 前缀 | 已修复，920 映射为 bj + market=103 |
| `ModuleNotFoundError: No module named 'kline_fetcher'` | 未安装包 | `pip install -e .` |
| 裸码 `000001` 取到的是指数不是平安银行 | 指数优先规则（代码歧义） | 个股用 `sz000001` 或显式 `market=0`，详见[API 参考](../api-reference.md#klinefetcher-基类) |
| 分钟K 09:30/13:00 没有数据 | API 用周期结束时刻标记（09:31~11:30、13:01~15:00） | 正常现象，日历已按 240 条/日对齐 |
| 在线调试服务打开 502 | 上游 API 请求失败或未配地址 | 检查 `KLINE_API_BASE_URL` 与服务端日志 |
