# Spider Hub

通用 Playwright 爬虫管理平台，后端拆成两个独立项目：

```text
master/
  调度 API、登录认证、slave node 管理、任务管理

slave/
  Playwright 浏览器环境运行时，只负责创建环境和执行采集

webui/
  Vue3 + Vite + TailwindCSS 管理控制台
```

默认部署只对外暴露 WebUI 端口 `8180`。浏览器登录 WebUI 后，WebUI 通过 Nginx 同源代理访问 master API；master 和 slave 在 Docker 内网通信。

## 环境变量

开发和生产配置模板：

```bash
.env.development.example
.env.production.example
```

生产部署建议先复制并修改：

```bash
cp .env.production.example .env
```

必须改掉这些值：

```text
SPIDER_MASTER_USERNAME
SPIDER_MASTER_PASSWORD
SPIDER_SESSION_SECRET
SPIDER_INTERNAL_API_TOKEN
```

`SPIDER_MASTER_USERNAME/PASSWORD` 用于 WebUI 登录；`SPIDER_INTERNAL_API_TOKEN` 只用于 slave 自动注册 master，不暴露给浏览器。

## Docker Compose

启动：

```bash
docker compose --env-file .env up -d --build
```

访问：

```text
WebUI: http://127.0.0.1:8180/
API:   http://127.0.0.1:8180/docs
```

默认账号密码来自 `.env`：

```text
SPIDER_MASTER_USERNAME=admin
SPIDER_MASTER_PASSWORD=...
```

查看日志：

```bash
docker compose logs -f spider-master
docker compose logs -f spider-webui
docker compose logs -f spider-slave
```

停止：

```bash
docker compose down
```

## Slave Node 数量

默认 compose 启动 1 个 slave node。每个 slave node 的 Playwright 环境上限由：

```text
SPIDER_SLAVE_MAX_ENVIRONMENTS=4
```

控制。多个 slave node 用 compose scale：

```bash
docker compose --env-file .env up -d --build --scale spider-slave=4
```

如果每个 node `SPIDER_SLAVE_MAX_ENVIRONMENTS=4`，4 个 node 总容量就是 16 个 Playwright 浏览器环境。

## 本地开发

启动 master：

```powershell
cd master
$env:SPIDER_ENV="development"
$env:SPIDER_MASTER_USERNAME="admin"
$env:SPIDER_MASTER_PASSWORD="admin"
$env:SPIDER_SESSION_SECRET="dev-session-secret"
$env:SPIDER_INTERNAL_API_TOKEN="dev-internal-token"
pip install -r requirements.txt
python -m src.server
```

启动 slave：

```powershell
cd slave
$env:SPIDER_ENV="development"
$env:SPIDER_INTERNAL_API_TOKEN="dev-internal-token"
$env:SPIDER_SLAVE_MASTER_URL="http://127.0.0.1:8000"
pip install -r requirements.txt
python -m playwright install chromium
python -m src.slave
```

启动 WebUI：

```powershell
cd webui
pnpm install
pnpm dev
```

开发代理默认转发到：

```text
http://127.0.0.1:8000
```

连接远程 master 时，在 `webui/.env.local` 中配置：

```text
VITE_API_PROXY_TARGET=http://192.168.1.221:8000
```

WebUI 顶部会显示当前 API 目标，并支持手动刷新和自动刷新间隔选择。

## API 登录

登录：

```bash
curl -X POST http://127.0.0.1:8180/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}'
```

后续 API 使用返回的 token：

```bash
curl http://127.0.0.1:8180/slaves \
  -H "Authorization: Bearer ACCESS_TOKEN"
```

WebUI 登录后会自动处理 token。浏览器打开 `/docs` 时使用同源登录 cookie。

## 创建 Playwright 环境

先打开 WebUI：

```text
http://127.0.0.1:8180/
```

点击 `新建环境`，选择目标 slave node，然后配置浏览器、代理、UA、语言、时区、分辨率、cookies 和 Chromium 启动参数。

master 不自动分配环境落点，创建环境时需要手动选择 slave node。

## 提交采集任务

异步任务：

```bash
curl -X POST http://127.0.0.1:8180/jobs \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ACCESS_TOKEN" \
  -d '{"url":"https://example.com/","wait_seconds":5,"include_html":true}'
```

同步抓取：

```bash
curl -X POST http://127.0.0.1:8180/fetch \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ACCESS_TOKEN" \
  -d '{"url":"https://example.com/","wait_seconds":5,"include_html":true}'
```

## 命名兼容

正式命名统一为 `slave` 和 `/slaves`。旧 `/slavers` API 路径仍保留为兼容入口。
