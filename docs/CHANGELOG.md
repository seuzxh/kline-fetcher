# Changelog

本文件记录本仓库（kline-fetcher monorepo：tzt-api + kline-qlib + 兼容壳）的版本变更。格式遵循 [Keep a Changelog](https://keepachangelog.com/)，版本号遵循 [Semantic Versioning](https://semver.org/)。

## [Unreleased]

### 🔧 重构

- **tzt-api 迁出为独立仓库 [GXQuant](https://github.com/seuzxh/GXQuant)**（2026-08-24，自 9b9613c 整体迁出）：行情客户端（4 个 Fetcher + `market.py` 单一事实源）及其测试、中焯官方文档归档（`docs/API/中焯官方文档/`）、概念板块接口文档（`concept_plate_api.md`）、原始抓包记录、tztapi-agent 指南均迁至 GXQuant。本仓保留 `kline-qlib` + `compat-kline-fetcher`，经 pip 依赖使用 `tzt-api>=1.0.0`（`import tzt_api` 用法不变）；mkdocs 导航移除已迁文档条目，相关链接改指 GXQuant 仓库

## [3.1.0] - 2026-08-23

### 🔧 重构

- **monorepo 双包拆分**：原单包 `kline-fetcher` 拆分为 `tzt-api`（纯行情请求，零 numpy，deps: requests/PyYAML）+ `kline-qlib`（qlib 写入，依赖 tzt-api，单向；CLI `kline-download`/`kline-server`）+ `compat-kline-fetcher`（旧包名兼容壳，3.1.0 终版，纯转发，deprecated，迁移完成后撤）
- **市场规则单一事实源**：`INDEX_CODE_MAP`/`infer_market` 等收敛至 `tzt_api/market.py`，两包共享
- **死键清理**：配置中失效键移除
- **CLI 迁移**：`kline-download` / `kline-server` 入口迁至 `kline-qlib` 包
- **旧路径兼容**：`from kline_fetcher import ...` 等全部旧导入路径经兼容壳保持可用

### 🐛 Bug 修复

- **`get_stock_concept_plates` 修复为可用**：旧实现复刻 iOS 抓包参数（10000 号请求 + 行情类 props），实测恒返回 `[]`。依据官方《行情3.0股票属性ID》改用**关联属性 `900|901|923`**（CoIndBlkIdx=行业 / CoBlkIdx=全部隶属板块 / RegionBlkIdx=地域）+ `{propID}.props=0|1|2`，一次请求返回全部所属板块，并按 900/923 交叉标注 `type`（industry/region/concept）。实测 688802/600519/sz000001 均正常（19~22 个板块）。签名变化：`market` 改为可选（自动推断），新增 `plate_type` 过滤参数（`"concept"/"industry"/"region"`）；kline-server 对应端点同步开放 `market`/`plate_type` 可选参数

### ✨ 新功能

- **kline-server 在线调试服务**（`server.py`）：FastAPI 薄包装，13 个只读 REST 端点（日K/分钟K/分时/概念板块/本地覆盖查询），`/docs` Swagger UI 浏览器在线测试。可选依赖 `pip install 'kline-fetcher[server]'`；NaN 序列化为 null，失败返回 502
- **factor 脏数据校验测试**：补齐 hfq 四价非正 / factor<1 整条置 NaN 场景的单元测试（校验逻辑本体已随指数系列提交入库）

### 📚 文档

- 项目文档整理至 `docs/`：新增 `architecture.md`（架构）、`design.md`（技术方案）、`api-reference.md`（API 参考）；CHANGELOG / REVIEW_ISSUES / 概念板块抓包文档迁入 `docs/`；README 增加文档索引

## [3.0.1] - 2026-07-06

### 🐛 Bug 修复

- **1min 日历对齐**：`_generate_1min_timestamps` 从 242 条改为 240 条（去掉 `09:30` 和 `13:00`），与中焯 API 实际返回数据对齐。API 不返回这两个时刻的数据，日历保留会导致对应位置永远写入 NaN。

### 🧪 测试

- 更新 `test_calendar_generation.py`：1min 断言 242→240，`09:30`/`13:00` 从"应包含"改为"不应包含"

---

## [3.0.0] - 2026-06-14

相较于 v2.0.2，本版本包含**破坏性 API 变更**（主版本号 +1）、**架构重构**、**新功能**和多个 **bug 修复**。

### 💥 破坏性变更

- **架构拆分**：原 `fetcher.py`（792 行单文件单类）拆分为多个文件，引入继承体系：
  - `KLineFetcher`（`_base.py`）：基类，含共享底座 + 日K方法
  - `MinKLineFetcher`（`min_kline.py`）：分钟K方法（继承 KLineFetcher）
  - `ConceptPlateFetcher`（`concept_plate.py`）：概念板块方法（继承 KLineFetcher）
  - `fetcher.py` 保留为兼容垫片（旧导入路径仍可用）
- **方法迁移**：`KLineFetcher` 基类不再直接含分钟K/概念板块方法，需用对应子类：
  - `fetch_min_kline` → `MinKLineFetcher`
  - `get_all_concept_plates` 等 → `ConceptPlateFetcher`
- **删除 `fetch_kline` 方法**：该方法存在隐蔽 bug（向后取 + 过早 starttime 会误定位返回最近数据）。中焯返回数据自带 `date`/`time` 字段，客户端可自行切片，该方法多余。

### ✨ 新功能

- **TrendFetcher 分时数据模块**（`trend.py`）：获取集合竞价 + 盘中分时数据（继承 KLineFetcher）

### 🔧 重构

- 提取 `_extract_stocks_per_h` helper，消除 4 处重复的 StocksPerH 解析（后随 #10 一并删除）
- 各模块补 `__all__` 声明与模块 docstring
- `download_min_kline` 改用 `MinKLineFetcher`，日K保持 `KLineFetcher`

### 🐛 Bug 修复

- **#3 `_build_min_arrays` 静默丢数据**：缺 `time` 字段时不再用 `00:00:00` 回退，改为显式跳过 + warning
- **#5 `download_min_kline` 停牌股重复下载**：跳过条件改为比较本地覆盖与 end 日历索引，容许 end 当天停牌
- **#6/#7 `_append_bin` 重叠覆盖风险**：重叠区改为「新数据非 NaN 才覆盖」，防止不完整数据用 NaN 覆盖旧有效值
- **#9 日历生成时刻缺失**：`_generate_1min_timestamps` / `_generate_5min_timestamps` 补含 `11:30`（上午收盘）和 `15:00`（全天收盘），覆盖率从 99.2%/95.8% 提升到 100%
- **#16 兼容垫片未导出子类**：`fetcher.py` 垫片补导 `MinKLineFetcher` / `ConceptPlateFetcher`

### 🧹 清理

- 删除 `_convert_volume` 的 `stocks_per_h` 死代码链路（含 `_extract_stocks_per_h` helper 和所有透传点）
- 删除 `UNKNOWN.egg-info/` 残留
- 移除硬编码 API 地址，改用 `KLINE_API_BASE_URL` 环境变量

### 📚 文档

- 修正数据源描述：AGENTS.md「东方财富 API」→「中焯行情 API」（笔误）
- 补充字段单位换算注释（实测确认：价格÷1e6、成交额÷1e4、成交量已是「股」）
- README / AGENTS.md 全面同步 v3.0.0 结构
- 新增 `REVIEW_ISSUES.md`：code review 待办跟踪

### 🧪 测试

- **49 个单元测试**（默认运行，无需 API）：
  - `test_append_bin.py`（9）：`_append_bin` 全场景含 NaN 保护
  - `test_build_min_arrays.py`（3）：缺 time 字段处理
  - `test_factor_calc.py`（6）：factor 数值正确性（mock 输入）
  - `test_calendar_generation.py`（13）：日历边界 11:30/15:00
  - `test_structure.py`（18）：包结构/导入/方法归属/静态方法
- **42 个集成测试 + 15 subtests**（需 API，默认跳过）：
  - `test_split_interfaces.py`（34）：三类 fetcher 端到端，覆盖各复权方式、5 种频率、错误输入
  - `test_concept_plates.py`（8 + 15 subtests）：概念板块 4 方法
  - `test_trend_*.py`：TrendFetcher 单元 + 集成测试
- pytest 配置：`integration` marker，默认 `addopts="-m 'not integration'"`

### ⬆️ 升级指南

从 v2.0.2 升级到 v3.0.0：

1. **导入路径**（旧代码兼容，无需改动）：
   ```python
   from kline_fetcher import KLineFetcher  # 仍可用
   ```
2. **方法调用**（需修改）：
   ```python
   # 旧（v2.0.2）→ 新（v3.0.0）
   fetcher = KLineFetcher()
   fetcher.fetch_min_kline(...)       → MinKLineFetcher().fetch_min_kline(...)
   fetcher.get_all_concept_plates()   → ConceptPlateFetcher().get_all_concept_plates(...)
   fetcher.fetch_kline(...)           → 删除，用 fetch_min_kline + 客户端切片
   ```
3. **环境变量**：确保设置 `KLINE_API_BASE_URL`（不再硬编码）

---

## [2.1.0] - 2026-06-14（内部过渡版本，未正式发布）

架构拆分（fetcher.py → _base/min_kline/concept_plate），含 #3/#16 修复。

## [2.0.2] - 2026-06-13

`_append_bin` start_idx 损坏修复（PR #2）。

## [2.0.1] - 2026-06-13

移除硬编码 API IP，改用环境变量（PR #1）。

## [2.0.0] - 2026-06-12

- 默认复权方式改为后复权（cqtype=2）
- 新增 `factor` 字段，移除 `amount` 字段
- `volume` 改为后复权成交量

## [1.0.0] - 初始版本
