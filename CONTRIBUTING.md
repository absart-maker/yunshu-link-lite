# 贡献指南

感谢你愿意参与 YunShu-Link Lite。本项目为学习用途的 MIT 开源改编版，
欢迎提交 Issue、PR 与想法。

## 如何开始

```bash
git clone https://github.com/absart-maker/yunshu-link-lite.git
cd yunshu-link-lite
```

核心引擎为纯 Python 标准库实现，无需安装第三方依赖即可验证：

```bash
cd main/xiaozhi-server
python -m engine.check
```

该命令会执行 51 项单元测试与 3 项运行场景（端到端演示、模拟设备协议、
真实 WebSocket 服务）。

## 提 PR 前请确认

- 代码可通过全库编译：`python -m compileall -q main/xiaozhi-server`
- 用例全部通过：`python -m engine.check`
- 新增/修改功能时补充对应测试（`engine/tests/`、`core/tests/`）
- 不提交本地运行配置（`main/xiaozhi-server/data/`）、密钥、模型缓存
- 遵守 MIT 许可：保留 [LICENSE](LICENSE) 中的版权声明与来源说明

## 提交规范

- 分支名：`feat/xxx`、`fix/xxx`、`docs/xxx`
- 提交信息：简洁一句话说明改动，例如
  `feat(engine): add streaming reply fallback`

## 架构简易地图

- `main/xiaozhi-server/engine/`：原创 AI 引擎层（契约、注册、编排、会话、
  传输、桥接）——改动重点
- `main/xiaozhi-server/core/`：与旧服务/配置的兼容层与接入点
- `main/manager-api`、`main/manager-web`：基于上游（MIT）的管理端

## 来源与许可

本项目改编自 [KingYeon-Zoo/YunShu-Link](https://github.com/KingYeon-Zoo/YunShu-Link)
（MIT），更上游为 `xinnan-tech/xiaozhi-esp32-server`（MIT）。`engine/` 为
本仓库原创实现。分发或商用请保留 MIT 许可与署名，详见 [LICENSE](LICENSE)。
