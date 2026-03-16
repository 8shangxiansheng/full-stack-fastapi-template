# 性能基线

`ISS-021` 用这套资产沉淀主链路压测基线，覆盖登录、菜单拉取、地址确认、加购、下单、支付回调与订单查询。

## 运行前提

1. 后端服务已启动，默认监听 `http://127.0.0.1:8000`。
2. 本地已执行演示种子：`bash scripts/seed-demo.sh`。
3. 环境中的 `PAYMENT_CALLBACK_SIGNING_SECRET` 与压测脚本使用的值一致。默认按仓库本地环境使用 `changethis`。

## 一键运行

优先使用本机 `k6`，未安装时自动回退到 Docker：

```bash
bash scripts/run-performance-baseline.sh
```

常用参数示例：

```bash
API_BASE_URL=http://127.0.0.1:8000/api/v1 K6_VUS=10 K6_DURATION=1m bash scripts/run-performance-baseline.sh
```

输出目录默认是 `performance/reports/<timestamp>/`，其中包含：

- `summary.json`：`k6` JSON 汇总。
- `summary.txt`：`k6` 控制台文本摘要。
- `report.md`：报告模板副本，方便补录实测数据。

## 指标建议

- `http_req_failed`：目标 `< 5%`
- `http_req_duration p95`：目标 `< 1200ms`
- 记录 DB CPU、连接数、慢查询数量
- 记录订单创建成功率、支付回调成功率
