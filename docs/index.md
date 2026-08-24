# kline-fetcher（qlib 数据管道）

A 股行情 → qlib bin 格式数据管道：本仓 `kline-qlib`（qlib 写入 + CLI）+ `compat-kline-fetcher`（旧包名兼容壳），行情客户端 `tzt-api` 位于独立仓库 [GXQuotes](https://github.com/seuzxh/GXQuotes)。基于中焯行情 API 获取行情数据，转换为 Qlib 标准 `.bin` 格式，供量化回测框架使用。无需 Token 认证，支持 `pip install` 安装。

## 核心能力

- **日 K 线**：支持 `begindate`/`enddate` 范围查询，>1500 条自动分段
- **分钟 K 线**：1min/5min/15min/30min/60min，`locator` 自动翻页
- **分时数据**：集合竞价（09:15-09:25）+ 盘中分时（09:30-15:00）
- **概念板块**：板块列表 / 板块K线 / 成份股
- **指数行情**：26 个常用指数白名单，裸码自动识别
- **qlib 转换**：对齐交易日历写入 bin，支持增量追加与覆盖检查
- **批量下载**：`kline-download` CLI，按股池增量更新
- **在线调试**：`kline-server` FastAPI Swagger UI 浏览器测试接口

## 安装与快速开始

```bash
pip install git+https://github.com/seuzxh/GXQuotes.git  # 先装行情客户端 tzt-api
pip install -e ./kline-qlib                            # 再装 qlib 写入包
pip install -e ./compat-kline-fetcher                  # 可选：旧包名兼容壳
pip install 'kline-qlib[server]'                       # 需要在线调试服务时
export KLINE_API_BASE_URL=...       # 必填，中焯行情 API 地址
```

```python
from tzt_api import KLineFetcher, MinKLineFetcher
from kline_qlib import KLineToQlib

fetcher = KLineFetcher()           # 日K线
data = fetcher.fetch_day_kline("600519", count=10)

min_fetcher = MinKLineFetcher()    # 分钟K线
min_data = min_fetcher.fetch_min_kline("600519", freq="5min", count=10)

converter = KLineToQlib()          # 写入 qlib bin
converter.day_kline_to_qlib("600519", data, mode="append")
```

## 文档导航

| 板块 | 内容 |
|------|------|
| [配置](guide/configuration.md) | 配置文件、环境变量、`.env` 与 GitHub Secrets |
| [批量下载](guide/download.md) | `kline-download` CLI 与 Python API |
| [在线调试服务](guide/server.md) | kline-server 启动与 Swagger UI 使用 |
| [数据格式](guide/data-format.md) | API 单位换算、qlib bin 编码、文件路径 |
| [使用示例](guide/usage.md) | 6 个典型场景（单股写入、增量更新、qlib 读取等） |
| [测试与兼容](guide/testing.md) | 单元/集成测试、v2.1.0 兼容说明、与 data/ 模块对比 |
| [常见问题](guide/faq.md) | 价格为负、返回 None 等问题排查 |
| [架构](architecture.md) | 模块划分、类继承、数据流、存储布局 |
| [技术方案](design.md) | 复权与 factor、增量追加、日历对齐等设计决策 |
| [API 参考](api-reference.md) | 全部公开类/方法/参数/返回值 |
| [GXQuotes 概念板块接口](https://github.com/seuzxh/GXQuotes/blob/master/docs/concept_plate_api.md) | 板块接口深度文档（随 tzt-api 迁至 GXQuotes） |
| [更新日志](CHANGELOG.md) | 版本变更记录 |

## 上手路线

- **第一次使用**：[配置](guide/configuration.md) → [使用示例](guide/usage.md) → [批量下载](guide/download.md)
- **排查数据问题**：[数据格式](guide/data-format.md) → [技术方案](design.md)（含数据正确性防线汇总）
- **查接口签名**：[API 参考](api-reference.md)
