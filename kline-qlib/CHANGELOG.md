# Changelog

本文件记录 kline-qlib 的版本变更（Keep a Changelog 格式）。

## [1.0.0] - 2026-08-23

- 自 kline-fetcher v3.0.1 拆分建包：converter（KLineToQlib）、download（含 kline-download/kline-server CLI）、server（FastAPI 调试服务）
- `code_to_qlib_dir` 收敛为对 tzt_api.market 的一行委托；删除 `download.PREFIX_TO_MARKET` 重复映射；`load_stock_pool` 不再实例化 KLineToQlib 取路径
- 依赖 numpy + tzt-api
