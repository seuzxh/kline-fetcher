# 配置

配置分三级：**环境变量 > 自定义配置文件 > 包内默认配置**（GXQuotes 仓库 `tzt_api/config/kline_config.yaml`，随 tzt-api 包安装）。

## 配置文件

构造 `KLineFetcher(config_path=...)` 可指定自定义配置；否则用 `KLINE_CONFIG_PATH` 环境变量，再退到包内默认：

```yaml
api:
  # 不要在这里填 base_url —— API 地址走 KLINE_API_BASE_URL 环境变量
  base_url: ""
  timeout: 10                # 请求超时（秒）
  max_retries: 3             # 最大重试次数（指数退避）
  retry_delay: 1             # 重试基础延迟（秒）
  request_interval: 0.1      # 限流：两次请求最小间隔（秒）

kline:
  cqtype: 2                  # 复权类型：0=不复权 1=前复权 2=后复权（默认，v2.0.0 起）
  day_count: -1500           # 日K默认获取条数（负数=从最新向前）
  min_count: -1500           # 分钟K默认获取条数
  outtype: 1
  rights: 0
  route: 1
  props: "0|1|2|3|4|191|190|519"
```

> 复权方式说明见[技术方案](../design.md#3-复权方案v200-起)：默认后复权 + `factor` 字段，历史数据不因除权失效，支持增量追加。

## 环境变量

| 环境变量 | 用途 | 默认值 |
|---------|------|-------|
| `KLINE_API_BASE_URL` | **API 服务地址**（优先于配置文件） | 无（必须配置） |
| `KLINE_CONFIG_PATH` | KLineFetcher 配置文件路径 | 包内 `config/kline_config.yaml` |
| `QLIB_DATA_DIR` | KLineToQlib 数据目录 | `/root/Projects/0.qlib_pro/qlib_data` |

> **安全说明**：API 地址（包含 IP/域名）不应硬编码在源代码或提交的配置文件中，请通过 `KLINE_API_BASE_URL` 环境变量传入。

## 本地开发（`.env` 文件）

项目 `.gitignore` 已忽略 `.env`，可在项目根目录创建：

```bash
# .env（不要提交到 Git）
KLINE_API_BASE_URL=http://<your-api-host>:<port>
```

使用 `python-dotenv` 等工具加载，或在启动脚本中手动导出：

```bash
export KLINE_API_BASE_URL=http://<your-api-host>:<port>
python your_script.py
```

## GitHub Actions / Secrets

在仓库 **Settings → Secrets and variables → Actions** 中添加：

- **Secret**（推荐，值不可见）：名称 `KLINE_API_BASE_URL`
- 或 **Variable**（值可见，适合非敏感配置）：名称 `KLINE_API_BASE_URL`

然后在 workflow 中通过 `env` 字段注入：

```yaml
jobs:
  fetch:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run kline fetcher
        env:
          KLINE_API_BASE_URL: ${{ secrets.KLINE_API_BASE_URL }}
          # 或使用 Variables: ${{ vars.KLINE_API_BASE_URL }}
```
