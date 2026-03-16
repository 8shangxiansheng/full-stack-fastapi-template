# ISS-20260303-021 主链路压测基线记录

更新时间：2026-03-16

## 本轮交付

1. 新增 `k6` 主链路压测脚本：`performance/k6/order-baseline.js`
2. 新增一键运行脚本：`scripts/run-performance-baseline.sh`
3. 新增报告模板：`performance/report-template.md`
4. 新增压测说明：`performance/README.md`
5. 在根文档补充压测入口：`README.md`

## 覆盖链路

- 登录
- 菜单查询
- 地址确认 / 创建
- 购物车清空与加购
- 下单
- 创建支付单
- 支付回调
- 订单详情查询

## 默认参数

- 用户：`demo@example.com`
- 密码：`changethis`
- 支付渠道：`mockpay`
- 场景：`5 VUs / 30s`
- 阈值：
  - `http_req_failed < 5%`
  - `http_req_duration p95 < 1200ms`

## 执行前置

1. 启动本地后端服务。
2. 执行演示种子：`bash scripts/seed-demo.sh`
3. 运行压测：`bash scripts/run-performance-baseline.sh`

## 校验结果

- `bash -n scripts/run-performance-baseline.sh`：通过。
- `curl -X POST /api/v1/login/access-token`：通过，确认本地后端链路可访问。
- `bash scripts/run-performance-baseline.sh`：已触发，脚本成功进入 Docker 回退分支，但首次拉取 `grafana/k6:0.49.0` 时因 `TLS handshake timeout` 未完成正式压测。
- 本机 `brew install k6` 后，已完成真实压测基线。
- 短冒烟基线：`1 VU / 5s`，`http_req_failed = 0%`，`p95 = 48.66ms`。
- 正式基线：`5 VUs / 30s`，`155` 次完整迭代，`1561` 个 HTTP 请求，`50.23 req/s`，`http_req_failed = 0%`，`p95 = 63.69ms`，`p90 = 53.01ms`，`max = 169.75ms`。

## 说明

- 运行脚本优先使用本机 `k6`。
- 若本机未安装 `k6`，自动回退到 `grafana/k6:0.49.0` Docker 镜像。
- Docker 回退模式下，会自动将 `localhost` / `127.0.0.1` 重写为 `host.docker.internal`，以便容器访问宿主机后端。
- 为兼容当前运行中的后端 API，脚本支持两套菜单读取路径：
  - 优先使用 `/api/v1/menu/dishes-with-skus`
  - 若接口不存在，则自动回退到 `/api/v1/menu/dishes` + `/api/v1/menu/dishes/{dish_id}/skus`
- 为避免多 VU 共享同一购物车造成“Cart is empty”竞争，脚本已改为在 `setup()` 阶段自动创建独立压测用户池，并按 VU 绑定账号。
- 本次正式结果已达到当前发布基线。
