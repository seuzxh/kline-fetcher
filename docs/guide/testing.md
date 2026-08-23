# 测试与兼容

## 测试

项目测试随各包独立存放（`tzt-api/tests/`、`kline-qlib/tests/`、`compat-kline-fetcher/tests/`），分两类。

### 单元测试（默认运行，无需 API）

```bash
cd tzt-api && pytest            # 行情请求包测试
cd kline-qlib && pytest         # qlib 写入包测试
cd compat-kline-fetcher && pytest  # 兼容壳转发测试
```

| 文件 | 覆盖内容 |
|------|---------|
| `test_append_bin.py` | `_append_bin` 增量合并逻辑（9 个场景，含 NaN 保护） |
| `test_build_min_arrays.py` | `_build_min_arrays` 缺 time 字段处理（3 个） |
| `test_factor_calc.py` | factor 数值正确性与脏数据置 NaN（10 个，mock 输入） |
| `test_calendar_generation.py` | 日历边界 11:30/15:00（13 个） |
| `test_structure.py` | 包结构/导入路径/方法归属/静态方法（18+ 个） |
| `test_server.py` | 在线调试服务（9 个，mock 上游） |

### 集成测试（需真实 API，默认跳过）

```bash
# 需先配置 API 地址
export KLINE_API_BASE_URL=http://<your-api-host>:<port>
cd tzt-api && pytest -m integration       # 显式启用集成测试（行情类）
```

- `test_split_interfaces.py`：三类 fetcher 端到端验证（覆盖各复权方式、5 种频率、错误输入、字段完整性、继承关系等）
- `test_concept_plates.py`：概念板块 4 个方法
- `test_indices_integration.py`：指数行情（26 个白名单防回归）
- `test_trend_*.py`：分时数据

集成测试通过 `integration` marker 标记，默认 `addopts="-m 'not integration'"` 确保无 API 环境下 CI 不失败。

## 向后兼容（v2.1.0 拆分）

v2.1.0 将原 `fetcher.py`（单文件单类）拆分为 `_base.py` / `min_kline.py` / `concept_plate.py`。v3.1.0 起进一步拆为 monorepo 双包（`tzt-api` + `kline-qlib`），旧导入路径经 `compat-kline-fetcher` 兼容壳仍可用：

```python
# 旧方式（兼容壳路径，仍可用；deprecated，迁移完成后撤）
from kline_fetcher.fetcher import KLineFetcher

# 新方式（v3.1.0+ 推荐，按包导入）
from tzt_api import KLineFetcher, MinKLineFetcher, ConceptPlateFetcher
```

**唯一破坏**：`KLineFetcher` 基类不再直接含分钟K/概念板块方法，需改用对应子类：

- `fetch_min_kline` → `MinKLineFetcher`
- `get_all_concept_plates` 等 → `ConceptPlateFetcher`

## 与 data/ 模块的区别

| 维度 | data/ (iFinD) | kline-fetcher (中焯 API) |
|------|--------------|------------------------|
| 数据源 | iFinD HTTP API | 中焯行情 API |
| 认证 | access_token + refresh_token | 无需认证 |
| 概念板块 | 支持 | 支持 |
| 批量查询 | 支持（多只股票一次请求） | 仅单只查询 |
| 额度限制 | 周额度/月额度（500万条/周） | 未知（暂无限制） |
| 复权方式 | 前复权/后复权可选 | 后复权（cqtype=2，v2.0.0 起）+ factor 字段 |
| 高频分页 | 不支持 | locator 自动翻页 |
| 大范围日K | 支持 | 分段下载（每段 ≤1500 条） |
| 安装方式 | 项目内模块 | `pip install -e ./tzt-api -e ./kline-qlib` |
