# ISS-20260303-012 质量收口与上线准备记录

更新时间：2026-03-03

## 本轮执行结果

- Backend 全量回归：通过。
- Frontend 构建：通过。
- Frontend Playwright E2E：未通过（环境阻塞，见下文）。

## 已执行命令与结果

1. `UV_CACHE_DIR=/tmp/uv-cache POSTGRES_PASSWORD=changethis uv run pytest tests/ -q`
- 结果：`87 passed, 33 warnings`。
- 说明：warning 主要为现有 Pydantic enum serialization 提示，不阻断发布。

2. `npm run build`（frontend）
- 结果：构建成功。
- 说明：存在 chunk size 提示（`index` chunk > 500 kB），为性能优化建议，非阻断项。

3. `npm run test`（frontend, Playwright）
- 结果：失败。
- 失败点：`tests/auth.setup.ts` 在登录后 `waitForURL("/")` 超时（30s）。
- 现象：浏览器与前端 webServer 已可启动，失败发生在登录闭环阶段，属于联调环境（后端/API 可达性或测试数据）阻塞。

## 本轮修复

1. 地址删除默认逻辑增强
- 文件：`backend/app/api/routes/addresses.py`
- 调整：删除地址后保证用户地址簿存在唯一默认地址；当删除的是默认地址时，重新选取最新地址为默认。

2. 地址测试稳定性修复
- 文件：`backend/tests/api/routes/test_addresses.py`
- 调整：在断言前调用 `db.expire_all()`，避免跨会话写入导致的 identity map 旧值误判。

## 发布前阻塞项（ISS-012 剩余）

1. 补齐 E2E 联调环境并重跑 Playwright
- 建议命令：`npm run test`（frontend）
- 通过标准：`62` 条 Playwright 用例全绿。

2. 压测执行与报告沉淀
- 当前仓库未内置专用压测脚本（如 k6/Locust）。
- 发布前建议至少补一版主链路压测（下单-支付-履约查询），并沉淀 QPS、P95、错误率、数据库负载指标。

## 上线清单（建议）

1. 数据库迁移到 head：`uv run alembic upgrade head`。
2. 后端回归：`uv run pytest tests/ -q`。
3. 前端构建：`npm run build`。
4. 前端 E2E：`npm run test`。
5. 核对关键配置：`POSTGRES_PASSWORD`、`FIRST_SUPERUSER_PASSWORD`、`SECRET_KEY`、`SENTRY_DSN`。
6. 灰度发布，监控错误率/订单创建成功率/支付回调成功率。

## 回滚清单（建议）

1. 应用回滚到上一稳定镜像。
2. 数据库按变更窗口决定：
- 若仅增量兼容迁移，可保留并回滚应用；
- 若涉及破坏性变更，执行对应 `alembic downgrade`。
3. 关键链路冒烟：登录、下单、支付、订单状态查询。
