# 架构拆分重构计划：monorepo 双包（tzt-api + kline-qlib）+ kline-fetcher 兼容壳

- **日期**：2026-08-23（本文档取代同日早先的单包分层方案 `refactor-plan-3.1.0.md`）
- **状态**：待实施（方案已确认，未开始改码）
- **方向决策**（用户确认）：
  1. **拆成两个项目**：`tzt-api`（仅行情请求）+ `kline-qlib`（qlib 写入）；
  2. **monorepo**：本仓库内两个发行包，不拆仓库；
  3. **旧路径先兼容**：旧 `kline-fetcher` 以兼容壳包保住全部旧导入路径，外部使用方（本机 3 个项目 6 处 import）零改动，后续择机迁移、最终撤壳。
- **版本规划**：`tzt-api 1.0.0`、`kline-qlib 1.0.0`、`kline-fetcher`（兼容壳）`3.1.0`（终版，标记 deprecated）。

---

## 一、背景与动机

项目当前混合两个职责——**行情 API 客户端**（获取数据）与 **qlib 数据转换下载**（消费数据）。勘察确认的混杂点：

| # | 问题 | 位置 | 性质 |
|---|------|------|------|
| 1 | **市场推断规则三份重复实现**：`infer_market`、`code_to_qlib_dir`（注释自认"需人工保持一致"）、`PREFIX_TO_MARKET` | `_base.py:199` / `converter.py:187` / `download.py:34` | 语义耦合，最易腐化 |
| 2 | `download.py` 同一函数内既调度 API 请求又做 qlib bin 写入 | `download.py:69,171` | 两职责交汇（拆包后天然归位） |
| 3 | `converter.ensure_calendar` 延迟导入 `kline_fetcher.fetcher` 垫片 | `converter.py:65` | 跨层依赖 |
| 4 | 配置死键：`kline_type_map` / `market_map` / `qlib_fields` 无代码读取 | `config/kline_config.yaml:17-37` | 配置与代码脱节 |
| 5 | `INDEX_CODE_MAP` 在 API 层定义、被 qlib 层消费 | `_base.py:108` → `converter.py:13` | 跨层共享无中立位置 |
| 6 | 垫片 `fetcher.py` 缺 `TrendFetcher` 导出 | `fetcher.py` | 历史缺口 |
| 7 | `load_stock_pool` 为拿路径实例化整个 `KLineToQlib` | `download.py:43` | 过重依赖 |
| 8 | **纯行情使用方被迫安装 numpy**（统一包依赖未隔离） | `pyproject.toml` | 拆包的直接动机 |

**外部使用方**（全在本机，兼容壳保证零改动）：

| 使用方 | 导入路径 |
|---|---|
| qlib/strategy1（2 处）、qlib/strategy2（1 处） | `from kline_fetcher import KLineFetcher` |
| rdagent/fetch_5min_for_pool.py | `from kline_fetcher.fetcher import KLineFetcher, MARKET_CODE_MAP` + `from kline_fetcher.converter import KLineToQlib` |
| rdagent/fetch_5min_data.py、prepare_plate_data.py | 包入口导入；后者版本校验 `==2.0.1` 本已失效 |

另有硬契约：CLI `kline-download` / `kline-server`、`uvicorn kline_fetcher.server:app`、13 个测试文件导入路径。

## 二、目标结构（monorepo）

```
kline-fetcher/                    ← 仓库名不变（避免 GitHub 远程重命名涟漪）
├── tzt-api/                      ← 包 ①：纯行情请求（零 numpy 依赖）
│   ├── pyproject.toml            #   name: tzt-api 1.0.0；deps: requests, PyYAML
│   ├── tzt_api/
│   │   ├── __init__.py           #   4 个 Fetcher + AdjustType
│   │   ├── market.py             #   ★市场规则单一事实源（两包共享，放行情侧）
│   │   ├── _base.py              #   KLineFetcher（市场判断委托 market.py）
│   │   ├── min_kline.py / concept_plate.py / trend.py
│   │   └── config/kline_config.yaml
│   ├── tests/                    #   行情侧单测 + 集成测试
│   └── CHANGELOG.md
├── kline-qlib/                   ← 包 ②：qlib 写入（依赖 tzt-api，单向）
│   ├── pyproject.toml            #   name: kline-qlib 1.0.0；deps: numpy, tzt-api；
│   │                             #   CLI: kline-download / kline-server；optional: server
│   ├── kline_qlib/
│   │   ├── __init__.py           #   KLineToQlib / download 函数 / POOL_MAP
│   │   ├── converter.py          #   KLineToQlib（code_to_qlib_dir 一行委托 market）
│   │   ├── download.py           #   下载编排 + CLI
│   │   └── server.py             #   调试服务（依赖两包，归写入侧）
│   ├── tests/                    #   转换/写入/服务侧单测 + 跨包一致性测试
│   └── CHANGELOG.md
├── compat-kline-fetcher/         ← 过渡兼容壳（后续撤）
│   ├── pyproject.toml            #   name: kline-fetcher 3.1.0；deps: tzt-api, kline-qlib
│   ├── kline_fetcher/            #   纯 re-export：__init__ / fetcher / converter / download / server
│   └── tests/                    #   旧路径回归测试
├── docs/ + mkdocs.yml            ← 文档站点覆盖全仓（含双包 API 参考）
├── AGENTS.md / README.md         ← 仓库级说明（monorepo 导览）
└── .github/workflows/            ← docs-pages.yml 不变
```

**依赖方向（单向，无环）**：`kline-qlib → tzt-api`；`compat-kline-fetcher → tzt-api + kline-qlib`。
`market.py` 归 tzt-api：qlib 侧经依赖取用，规则仍单一事实源。

**收益**：
- 职责物理隔离：行情请求包无 numpy、无 qlib 概念；qlib 写入包不含 HTTP 客户端实现
- 兼容壳保旧路径：本机 3 个项目 6 处 import 零改动，迁移节奏自定
- market.py 消灭三份市场推断重复；两包各自可独立测试、独立演进版本

## 三、实施阶段

**本次实施（任务分解见 [superpowers/plans/2026-08-23-monorepo-split.md](superpowers/plans/2026-08-23-monorepo-split.md)，7 个任务）**：

1. **tzt-api 包成型**：market.py 单一事实源 + 4 个 Fetcher 模块 + config 迁入 + 行情侧测试归位；根 `kline_fetcher` 即时垫片化保绿
2. **kline-qlib 包成型**：converter/download/server 迁入 + CLI 入口 + 写入侧测试归位；根 converter/download 垫片化
3. **兼容壳独立成包**：根 `kline_fetcher/` 整体迁为 `compat-kline-fetcher/`，删根 pyproject，monorepo 收拢
4. **去重收敛**：`code_to_qlib_dir` 一行化（tzt_api.market 委托）、删 `PREFIX_TO_MARKET`、`load_stock_pool` 轻量化 + 跨包一致性测试
5. **配置死键删除 + 三包 CHANGELOG**
6. **文档全站同步**（AGENTS/README/docs/mkdocs）
7. **全量验证**（三包安装、三套 pytest、CLI smoke、旧路径模拟、可选集成测试）

**后续阶段（不在本次，另行任务）**：

- 迁移本机 6 处使用方到新包名（顺手修 rdagent 失效的版本校验）→ 撤兼容壳
- 视需要再评估：是否拆两仓库（monorepo 已给足隔离，拆仓库收益待定）

## 四、兼容性保证（兼容壳覆盖全部旧路径）

| 旧路径 / 入口 | 兼容方式 |
|---|---|
| `from kline_fetcher import KLineFetcher, MinKLineFetcher, ConceptPlateFetcher, TrendFetcher, KLineToQlib, AdjustType` | 壳 `__init__` re-export（tzt_api + kline_qlib） |
| `from kline_fetcher.fetcher import ...`（含 `MARKET_CODE_MAP`） | 壳内 `fetcher.py` 转发 tzt_api（补 TrendFetcher） |
| `from kline_fetcher.converter import KLineToQlib, QLIB_*_FIELDS` | 壳内 `converter.py` 转发 kline_qlib |
| `from kline_fetcher.download import download_*, load_stock_pool, POOL_MAP, main` | 壳内 `download.py` 转发 kline_qlib |
| `uvicorn kline_fetcher.server:app` / `kline-server` | 壳内 `server.py` 转发；CLI 实际入口在 kline-qlib |
| `kline-download` / `kline-server` CLI | kline-qlib 的 `[project.scripts]` |
| `kline_fetcher.__version__` | `"3.1.0"`（终版；docstring 标注 deprecated，不发运行时警告避免污染日志） |

**语义变化（有意为之）**：`KLineFetcher.__module__` 变为 `"tzt_api._base"`——仅本项目测试断言，随测试更新；外部无依赖。

## 五、验证（qlib conda 环境）

1. 三包可编辑安装：`pip install -e ./tzt-api -e ./kline-qlib -e ./compat-kline-fetcher`
2. 三套测试：各包目录内 `pytest -q`（默认排除 integration）
3. CLI smoke：`kline-download --help`、`kline-server --help`
4. 旧路径全量模拟（含 rdagent 的混合导入）
5. 依赖隔离验证：tzt-api 环境 `pip show tzt-api` 确认无 numpy 依赖
6. 可选：`KLINE_API_BASE_URL=... pytest -m integration -k indices`（真实 API 行为不变）
7. `mkdocs build --strict`

## 六、风险与规避

| 风险 | 规避 |
|---|---|
| 根包垫片化期间的断链 | 任务 1/2 内"搬迁+垫片"同 commit 完成，每任务全测试绿再提交 |
| 本地包互相依赖解析 | 三包一条命令可编辑安装；kline-qlib 依赖 `tzt-api>=1.0.0` 由已装发行版满足 |
| editable entry_points 过期 | 任务 7 重装后 smoke；旧根 egg-info/`build/` 残留清理 |
| 行为漂移 | converter/download 只改导入与查表来源，控制流不动；`code_to_qlib_dir` 一行化由跨包一致性测试锁定 |
| mkdocs strict 构建失败 | 文档任务末尾本地 strict 验证 |

## 七、明确不做的事（Scope 边界）

- 不拆两个仓库（monorepo 内双包已满足隔离）
- 本次不改 6 处外部使用方（兼容壳兜底；迁移+撤壳为后续独立任务）
- 不重写 download.py 编排控制流（分段/增量/限流原样）
- 死配置键直接删（不做"配置驱动常量"的行为变更）
- 兼容壳不发 DeprecationWarning 运行时警告（避免兄弟项目日志污染；docstring + 文档标注）
- 仓库名/GitHub 远程不改名
