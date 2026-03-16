# ISS-20260303-023 配置安全收口记录

更新时间：2026-03-16

## 本轮交付

1. 新增统一密钥治理脚本：`scripts/security-gate.sh`
2. 新增后端安全配置检查入口：`backend/app/check_security_config.py`
3. 将受治理密钥集中定义在 `backend/app/core/config.py`
4. 将安全治理接入 `release-gate`
5. 将部署 workflow 补齐 `PAYMENT_CALLBACK_SIGNING_SECRET` 并在部署前执行 `strict` 检查

## 受治理密钥

- `SECRET_KEY`
- `POSTGRES_PASSWORD`
- `FIRST_SUPERUSER_PASSWORD`
- `PAYMENT_CALLBACK_SIGNING_SECRET`

## 运行方式

```bash
bash scripts/security-gate.sh warn
bash scripts/security-gate.sh strict
RELEASE_SECURITY_MODE=strict bash scripts/release-gate.sh full
```

## 模式说明

- `warn`
  - 适合本地开发
  - 打印默认密钥风险但不阻断
- `strict`
  - 适合发布前、部署前、CI/CD
  - 发现默认密钥或过短签名密钥时直接失败
