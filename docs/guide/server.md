# 在线调试服务（Swagger UI）

`server.py` 提供基于 FastAPI 的在线接口测试页面，把各 Fetcher 方法暴露为 REST 端点，浏览器里填参数即可测试，无需写脚本或 Postman。

## 安装与启动

```bash
pip install 'kline-fetcher[server]'   # 安装 fastapi + uvicorn 可选依赖

export KLINE_API_BASE_URL=...         # 数据获取类端点需要
kline-server                          # 默认 http://127.0.0.1:8000/docs
kline-server --port 9000              # 自定义端口
uvicorn kline_fetcher.server:app      # 等效启动方式
```

## 页面

- **`/docs`**：Swagger UI，可交互测试（填参数 → Try it out → 看 JSON 响应）
- **`/redoc`**：ReDoc 接口文档

端点按模块分组：

| 分组 | 端点 |
|------|------|
| 日K线 | `/api/day-kline`、`/api/day-kline-with-factor`、`/api/trade-calendar`、`/api/stock-info` |
| 分钟K线 | `/api/min-kline` |
| 分时数据 | `/api/trend`、`/api/trend/intraday`、`/api/trend/history` |
| 概念板块 | `/api/concept/plates`、`/api/concept/plate-kline`、`/api/concept/plate-stocks`、`/api/concept/stock-plates` |
| 本地数据查询 | `/api/coverage`（本地 bin 覆盖检查，只读） |

## 行为约定

- 参数与 Python API 一致（日期格式 `YYYYMMDD`、频率枚举、复权枚举均有表单校验，非法返回 422）
- 请求失败返回 502 并附说明，原因见服务端日志
- 脏数据记录中的 NaN 序列化为 `null`
- **只暴露读操作**，不提供 bin 写入端点，防止误写数据

## 安全提示

服务无鉴权（中焯 API 本身无 Token），默认只绑定 `127.0.0.1`。团队内网共享用 `kline-server --host <内网IP>`，并做好网络层访问控制；**请勿直接暴露公网**。

完整端点参数说明见 [API 参考](../api-reference.md#server-在线调试服务)。
