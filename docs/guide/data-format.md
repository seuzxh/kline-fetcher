# 数据格式

## API 原始数据单位转换

中焯 API 原始字段单位与直觉不同，取数层统一换算（实测依据见[技术方案](../design.md#13-字段单位换算实测确认)）：

| 字段 | API 原始字段 | 原始单位 | 转换公式 | 目标单位 |
|------|------------|---------|---------|---------|
| 开盘价 | OpenPrice | 万分之一元 | ÷ 1,000,000 | 元 |
| 最高价 | HighPrice | 万分之一元 | ÷ 1,000,000 | 元 |
| 最低价 | LowPrice | 万分之一元 | ÷ 1,000,000 | 元 |
| 收盘价 | ClosePrice | 万分之一元 | ÷ 1,000,000 | 元 |
| 成交量 | PeriodVolume | 股 | 直接使用 | 股 |
| 成交额 | PeriodTurnover | 万元 | ÷ 10,000 | 元 |
| 时间 | Time | 14 位整数 | 格式化 | YYYY-MM-DD [HH:MM:SS] |

## qlib bin 文件格式

- **编码**：float32 小端序（`<f`）
- **结构**：`[start_idx, data[0], data[1], ..., data[n-1]]`
- **start_idx**：数据在交易日历中的起始索引
- **对齐**：数据按交易日历对齐，非交易日/停牌/脏数据槽位为 NaN
- **VWAP**：由 `amount / volume` 计算，volume=0 时为 NaN

## 文件路径规则

| 数据类型 | 路径模板 | 示例 |
|---------|---------|------|
| 日K | `{qlib_data_dir}/features/{qlib_dir}/{field}.day.bin` | `qlib_data/features/sh600519/close.day.bin` |
| 1min | `{qlib_data_dir}/features/{qlib_dir}/{field}.1min.bin` | `qlib_data/features/sh600519/close.1min.bin` |
| 5min | `{qlib_data_dir}/features/{qlib_dir}/{field}.5min.bin` | `qlib_data/features/sh600519/close.5min.bin` |

`qlib_dir` 命名：`sh600519`、`sz000001`、`bj830799`（指数白名单按指数所属市场，如沪深300 → `sh000300`）。

## 写入字段

`open`, `high`, `low`, `close`, `volume`, `factor`, `vwap`（`amount` 仅作为 vwap 计算的中间量，不落盘）。

## 复权与 factor

存储价格 = 后复权价格，`factor = 后复权收盘价 / 不复权收盘价`（恒 ≥ 1）：

- 还原原始价格：`原始价 = 后复权价 / factor`
- 还原原始成交量：`原始成交量 = 后复权成交量 × factor`

脏数据（四价非正、factor<1）整条置 NaN，详见[技术方案](../design.md#33-脏数据防御2026-08-增强)。
