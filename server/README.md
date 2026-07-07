# Spider Master Backend

这是一个通用 Playwright 爬虫管理后台。后台只需要启动 `master`，然后通过 WebUI 或 HTTP API 创建/注册 `slaver task`。每个 slaver task 持有一个浏览器实例，等待 master 下发 URL 采集任务。

```text
master
  提供 WebUI 和 HTTP API
  管理 slaver task 环境
  按策略调度 URL 任务
  保存内存中的任务状态和结果

slaver task
  一个 Playwright 浏览器环境
  由某个 slaver node 承载
  抓取页面源码、链接、标题、状态码等
  通过 HTTP 返回给 master

slaver node
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

如果要使用本机 Chrome 或 Edge，可以在新建 slaver 环境时选择 `chrome` 或 `msedge`。

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
WebUI: http://127.0.0.1:8080/
API:   http://127.0.0.1:8000/docs
```

查看日志：

```powershell
docker compose logs -f spider-master
docker compose logs -f spider-webui
docker compose logs -f spider-slaver
```

停止：

```powershell
docker compose down
```

Compose 会启动三个服务：

```text
spider-master  后端 master/API，端口 8000，轻量调度端
spider-webui   前端 Vue/Nginx，端口 8080
spider-slaver  Playwright 采集节点，默认不暴露宿主机端口，单节点可承载多个浏览器，可横向扩容
```

`spider-slaver` 启动后会自动向 `spider-master` 注册。当前 compose 里每个 slaver node 默认 `--max-workers 4`，也就是单个 slaver 容器最多创建 4 个 Playwright 浏览器环境。

新建 Playwright 环境时需要在 WebUI 里手动选择目标 slaver node，master 不会自动分配。这样可以按节点资源、代理段、机房或业务用途来控制环境落点。

需要更多采集容量时有两种方式：

```text
增加单节点容量：调大 spider-slaver 的 --max-workers 和资源限制
增加节点数量：横向扩 spider-slaver 容器副本
```

横向扩容示例：

```powershell
docker compose up -d --build --scale spider-slaver=4
```

master 和 WebUI 通常资源占用较小；slaver 会启动浏览器，建议把 CPU、内存和 `shm_size` 主要分给 slaver。`docker-compose.yml` 里已经给 master 和 slaver 分开写了基础资源限制，可按机器配置调整。

## 5. 通过 WebUI 添加 Slaver Task

打开：

```text
http://127.0.0.1:8080/
```

点击 `新建环境`，可以配置：

```text
基础设置：环境名称、启动 host、端口、浏览器类型、有头模式、额外等待秒数、User Agent、语言、时区、分辨率
代理信息：HTTP / HTTPS / SOCKS5、代理主机、端口、账号、密码
账号信息：Playwright cookies JSON
高级设置：Chromium 启动参数、禁止加载图片、禁止加载音视频
```

也可以注册已经独立启动的 slaver：

```text
http://127.0.0.1:8101
```

## 6. 通过 HTTP API 添加 Slaver Task

在指定 slaver node 上创建一个 Playwright 环境：

```powershell
curl -X POST http://127.0.0.1:8000/slavers/start ^
  -H "Content-Type: application/json" ^
  -d "{\"node_id\":\"NODE_ID\",\"env_name\":\"crawler-1\",\"headful\":true,\"browser_channel\":\"chrome\",\"challenge_wait\":5}"
```

带代理和启动参数：

```powershell
curl -X POST http://127.0.0.1:8000/slavers/start ^
  -H "Content-Type: application/json" ^
  -d "{\"node_id\":\"NODE_ID\",\"env_name\":\"crawler-1\",\"headful\":true,\"browser_channel\":\"chrome\",\"challenge_wait\":5,\"proxy\":{\"enabled\":true,\"scheme\":\"http\",\"host\":\"127.0.0.1\",\"port\":3128,\"username\":\"user\",\"password\":\"pass\"},\"launch_args\":[\"--disable-notifications\"],\"locale\":\"en-US\",\"timezone_id\":\"UTC\",\"viewport_width\":1365,\"viewport_height\":768,\"block_images\":false,\"block_media\":false}"
```

查看 slaver：

```powershell
curl "http://127.0.0.1:8000/slavers?refresh=true"
```

删除 slaver：

```powershell
curl -X DELETE http://127.0.0.1:8000/slavers/slaver-8101
```

如果是 master 启动的托管 slaver，删除时会终止对应子进程。

## 7. 手动启动并注册远程 Slaver

在 slaver 所在机器运行：

```powershell
cd D:\workspace\gitlab\spider\server
python -m src.slaver --host 0.0.0.0 --port 8101 --headful --browser-channel chrome --challenge-wait 5
```

然后在 master 注册：

```powershell
curl -X POST http://127.0.0.1:8000/slavers ^
  -H "Content-Type: application/json" ^
  -d "{\"base_url\":\"http://SLAVER_IP:8101\"}"
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

指定某个 slaver：

```powershell
curl -X POST http://127.0.0.1:8000/jobs ^
  -H "Content-Type: application/json" ^
  -d "{\"url\":\"https://example.com/\",\"worker_id\":\"slaver-8101\",\"wait_seconds\":5}"
```

## 9. Master 参数

```text
--host              master 监听地址，默认 127.0.0.1
--port              master 监听端口，默认 8000
--strategy          默认调度策略：round_robin / random / sticky
--challenge-wait    页面加载后的默认额外等待秒数，默认 0
--headful           master 启动托管 slaver 时默认显示浏览器窗口
--browser-channel   master 启动托管 slaver 时默认使用 chrome 或 msedge
```

## 10. 调度策略

```text
round_robin  按顺序轮询 slaver
random       随机选择 slaver
sticky       总是选择第一个 slaver
```

如果请求中传了 `worker_id`，会优先使用指定 slaver，忽略策略。

## 11. 常见问题

没有 slaver 时提交任务会失败：

```text
no running workers
```

解决：先在 WebUI 启动或注册一个 slaver。

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
