# Spider Master Backend

这是一个通用 Playwright 爬虫管理后台。后台只需要启动 `master`，然后通过 WebUI 或 HTTP API 创建/注册 `slave task`。每个 slave task 持有一个浏览器实例，等待 master 下发 URL 采集任务。

```text
master
  提供 WebUI 和 HTTP API
  管理 slave task 环境
  按策略调度 URL 任务
  保存内存中的任务状态和结果

slave task
  一个 Playwright 浏览器环境
  由某个 slave node 承载
  抓取页面源码、链接、标题、状态码等
  通过 HTTP 返回给 master

slave node
  一个采集节点，可以是一个容器或一台机器
  一个 node 内可以创建多个 Playwright 浏览器环境
  node 负责真正启动和持有浏览器
```

## 1. 安装依赖

```powershell
cd D:\workspace\gitlab\spider\server
pip install -r requirements.txt
python -m playwright install chromium
```

只启动 master 做调度时不需要安装 Playwright 浏览器，可以用轻量依赖：

```powershell
pip install -r requirements-master.txt
```

启动 slave 采集节点时才需要 Playwright：

```powershell
pip install -r requirements-slave.txt
python -m playwright install chromium
```

如果要使用本机 Chrome 或 Edge，可以在新建 slave 环境时选择 `chrome` 或 `msedge`。

## 2. 构建 WebUI

```powershell
cd D:\workspace\gitlab\spider\webui
pnpm install
pnpm build
```

构建产物输出到 `webui/dist`，master 会优先加载它。

前端开发模式：

```powershell
pnpm dev
```

开发地址：

```text
http://127.0.0.1:5173/
```

## 3. 启动 Master

```powershell
cd D:\workspace\gitlab\spider\server
python -m src.server --host 127.0.0.1 --port 8000
```

WebUI：

```text
http://127.0.0.1:8000/
```

API 文档：

```text
http://127.0.0.1:8000/docs
```

健康检查：

```powershell
curl http://127.0.0.1:8000/health
```

## 4. Docker Compose 启动

在项目根目录运行：

```powershell
docker compose up -d --build
```

访问：

```text
WebUI: http://127.0.0.1:8180/
API:   http://127.0.0.1:8000/docs
```

查看日志：

```powershell
docker compose logs -f spider-master
docker compose logs -f spider-webui
docker compose logs -f spider-slave
```

停止：

```powershell
docker compose down
```

Compose 会启动三个服务：

```text
spider-master  后端 master/API，端口 8000，轻量调度端，不安装 Playwright 浏览器
spider-webui   前端 Vue/Nginx，端口 8180
spider-slave  Playwright 采集节点，默认不暴露宿主机端口，使用预装浏览器镜像，单节点可承载多个浏览器，可横向扩容
```

`spider-slave` 启动后会自动向 `spider-master` 注册。默认 compose 只启动 1 个 slave node；每个 slave node 默认 `--max-environments 4`，也就是单个 slave 容器最多创建 4 个 Playwright 浏览器环境。

新建 Playwright 环境时需要在 WebUI 里手动选择目标 slave node，master 不会自动分配。这样可以按节点资源、代理段、机房或业务用途来控制环境落点。

需要更多采集容量时有两种方式：

```text
增加单节点 Playwright 环境容量：调大 spider-slave 的 --max-environments 和资源限制
增加 slave node 数量：横向扩 spider-slave 容器副本
```

横向扩容示例：

```powershell
docker compose up -d --build --scale spider-slave=4
```

上面命令会启动 4 个 slave node；如果每个 node 仍然是 `--max-environments 4`，总共最多可创建 16 个 Playwright 浏览器环境。`--max-environments` 不是 node 数量，它只限制单个 slave node 内能创建多少个 Playwright 环境。

master 和 WebUI 通常资源占用较小；slave 会启动浏览器，建议把 CPU、内存和 `shm_size` 主要分给 slave。`docker-compose.yml` 里已经给 master 和 slave 分开写了基础资源限制，可按机器配置调整。

首次执行 `docker compose up -d --build` 慢、日志多是正常的：Docker 会拉 Python、Nginx、Playwright 基础镜像，并安装 Python 依赖。以前 master 和 slave 共用一个 Dockerfile，master 也会执行 Playwright/Chromium 安装，所以日志尤其多；现在已经拆成 `Dockerfile.master` 和 `Dockerfile.slave`，master 镜像会轻很多。后续没有改依赖时会命中缓存，启动会明显变快。

如果只想看服务运行日志，不看构建过程：

```powershell
docker compose up -d
docker compose logs -f spider-master
```

## 5. 通过 WebUI 添加 slave Task

打开：

```text
http://127.0.0.1:8180/
```

点击 `新建环境`，可以配置：

```text
基础设置：环境名称、启动 host、端口、浏览器类型、有头模式、额外等待秒数、User Agent、语言、时区、分辨率
代理信息：HTTP / HTTPS / SOCKS5、代理主机、端口、账号、密码
账号信息：Playwright cookies JSON
高级设置：Chromium 启动参数、禁止加载图片、禁止加载音视频
```

也可以注册已经独立启动的 slave：

```text
http://127.0.0.1:8101
```

## 6. 通过 HTTP API 添加 slave Task

在指定 slave node 上创建一个 Playwright 环境：

```powershell
curl -X POST http://127.0.0.1:8000/slaves/start ^
  -H "Content-Type: application/json" ^
  -d "{\"node_id\":\"NODE_ID\",\"env_name\":\"crawler-1\",\"headful\":true,\"browser_channel\":\"chrome\",\"challenge_wait\":5}"
```

带代理和启动参数：

```powershell
curl -X POST http://127.0.0.1:8000/slaves/start ^
  -H "Content-Type: application/json" ^
  -d "{\"node_id\":\"NODE_ID\",\"env_name\":\"crawler-1\",\"headful\":true,\"browser_channel\":\"chrome\",\"challenge_wait\":5,\"proxy\":{\"enabled\":true,\"scheme\":\"http\",\"host\":\"127.0.0.1\",\"port\":3128,\"username\":\"user\",\"password\":\"pass\"},\"launch_args\":[\"--disable-notifications\"],\"locale\":\"en-US\",\"timezone_id\":\"UTC\",\"viewport_width\":1365,\"viewport_height\":768,\"block_images\":false,\"block_media\":false}"
```

查看 slave：

```powershell
curl "http://127.0.0.1:8000/slaves?refresh=true"
```

旧版 `/slavers` API 路径仍然保留为兼容入口，但新代码和文档统一使用 `/slaves`。

删除 slave：

```powershell
curl -X DELETE http://127.0.0.1:8000/slaves/slave-8101
```

如果是 master 启动的托管 slave，删除时会终止对应子进程。

## 7. 手动启动并注册远程 slave

在 slave 所在机器运行：

```powershell
cd D:\workspace\gitlab\spider\server
python -m src.slave --host 0.0.0.0 --port 8101 --headful --browser-channel chrome --challenge-wait 5
```

然后在 master 注册：

```powershell
curl -X POST http://127.0.0.1:8000/slaves ^
  -H "Content-Type: application/json" ^
  -d "{\"base_url\":\"http://slave_IP:8101\"}"
```

## 8. 提交采集任务

HTTP 异步任务：

```powershell
curl -X POST http://127.0.0.1:8000/jobs ^
  -H "Content-Type: application/json" ^
  -d "{\"url\":\"https://example.com/\",\"wait_seconds\":5,\"include_html\":true}"
```

查看任务：

```powershell
curl http://127.0.0.1:8000/jobs
curl http://127.0.0.1:8000/jobs/JOB_ID
```

同步抓取并等待结果：

```powershell
curl -X POST http://127.0.0.1:8000/fetch ^
  -H "Content-Type: application/json" ^
  -d "{\"url\":\"https://example.com/\",\"wait_seconds\":5,\"include_html\":true}"
```

指定某个 slave：

```powershell
curl -X POST http://127.0.0.1:8000/jobs ^
  -H "Content-Type: application/json" ^
  -d "{\"url\":\"https://example.com/\",\"worker_id\":\"slave-8101\",\"wait_seconds\":5}"
```

## 9. Master 参数

```text
--host              master 监听地址，默认 127.0.0.1
--port              master 监听端口，默认 8000
--strategy          默认调度策略：round_robin / random / sticky
--challenge-wait    页面加载后的默认额外等待秒数，默认 0
--headful           master 启动托管 slave 时默认显示浏览器窗口
--browser-channel   master 启动托管 slave 时默认使用 chrome 或 msedge
```

## 10. 调度策略

```text
round_robin  按顺序轮询 slave
random       随机选择 slave
sticky       总是选择第一个 slave
```

如果请求中传了 `worker_id`，会优先使用指定 slave，忽略策略。

## 11. 常见问题

没有 slave 时提交任务会失败：

```text
no running workers
```

解决：先在 WebUI 启动或注册一个 slave。

页面需要等待异步渲染：

```text
调大 challenge_wait，例如 5、10 或 30
使用 --headful --browser-channel chrome 观察页面
```

WebUI 没有更新：

```powershell
cd D:\workspace\gitlab\spider\webui
pnpm build
```

然后重启 master。
