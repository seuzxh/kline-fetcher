# Changelog

## [3.1.0] - 2026-08-23

- **终版（deprecated）**：原 kline-fetcher 统一包拆分为 tzt-api + kline-qlib 后，本包仅保留旧导入路径转发（包入口 / fetcher / converter / download / server 垫片），不再演进
- `fetcher` 垫片补上 v2.1.0 遗漏的 `TrendFetcher` 导出
- 使用方迁移完成后本包可卸载删除
