# Changelog

本文件记录 tzt-api 的版本变更（Keep a Changelog 格式）。

## [1.0.0] - 2026-08-23

- 自 kline-fetcher v3.0.1 拆分建包：KLineFetcher/_base、MinKLineFetcher、ConceptPlateFetcher、TrendFetcher 及 config
- 新增 `tzt_api.market` 市场规则单一事实源（原 `_base` 常量与 infer_market/is_index/get_index_info 纯函数化；`KLineFetcher` 对应静态方法改为委托）
- 依赖仅 requests + PyYAML（不再连带 numpy）
