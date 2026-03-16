# ISS-20260303-022 统一发布前门禁脚本记录

更新时间：2026-03-16

## 本轮交付

1. 新增统一门禁脚本：`scripts/release-gate.sh`
2. 支持 `fast` / `full` 两种模式
3. 更新路线台账与 TODO 状态
4. 在根文档补充发布前门禁入口

## 门禁范围

- Docker Compose 本地栈拉起与健康检查
- Backend 健康检查
- Frontend 健康检查
- OpenAPI 生成与前端客户端同步
- Backend `pytest`
- Frontend `build`
- Playwright E2E（仅 `full` 模式）

## 使用方式

```bash
bash scripts/release-gate.sh fast
bash scripts/release-gate.sh full
```

## 模式说明

- `fast`
  - 适合本地日常回归
  - 跳过 Playwright
- `full`
  - 适合发布前最终门禁
  - 包含 Playwright 全量联调

## 设计约束

- 复用当前本地 Compose 栈，不额外起第二套环境，避免端口冲突。
- 不主动 `down` 当前开发栈，避免打断本地联调。
- 默认使用 `compose.yml + compose.override.yml`，对齐本地开发实际启动方式。

## 本轮验证

- `bash -n scripts/release-gate.sh`：通过
- `bash scripts/release-gate.sh fast`：通过
- 本次 `fast` 结果：
  - Compose 栈健康检查通过
  - Backend 健康检查通过
  - Frontend 健康检查通过
  - OpenAPI 客户端生成通过
  - Backend `pytest`：`96 passed`
  - Frontend `build`：通过
