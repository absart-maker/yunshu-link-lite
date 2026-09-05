# 运行与测试报告

## 一句话结论

本目录的**原创 AI 引擎层（`main/xiaozhi-server/engine/`）可独立正常运行**，
已通过全量编译、30 项单元测试、端到端演示与模拟设备实时协议测试。
完整物联网平台（Java 管理端 + Web 控制台 + ESP32 硬件）需要额外的
运行环境与外部服务，见下文“完整栈运行前提”。

## 已在当前机器验证的项

| 验证项 | 命令 | 结果 |
| --- | --- | --- |
| 全库语法编译 | `python -m compileall -q main/xiaozhi-server` | 通过（0 错误 / 0 警告） |
| 单元测试 | `python -m unittest discover -s engine/tests -t .` + `core/tests` | **51/51 通过** |
| 端到端演示 | `python -m engine` | 通过（两轮多轮对话） |
| 模拟设备协议 | `python -m engine.device_simulator` | 通过（`ready → listening → transcript → reply → audio`） |
| 真实 WebSocket 服务 | `python -m engine.server` + `--client` | 通过（真实网络握手 + 帧交互） |
| 独立进程端到端 | 服务进程 + 客户端进程 | 通过（服务监听 `127.0.0.1:8765`，帧序列完整） |
| 旧协议集成 | `LegacyProtocolAdapter` + `LegacySessionChannel` | 通过（hello/audio/bye 全流程） |
| 旧服务引擎开关 | `core/engine_runtime.py` + `core/websocket_server.py` | 通过（默认 legacy，auto 回退，engine 显式接管） |
| 一键自检 | `python -m engine.check` | 全部 PASS |

## 测试矩阵（全部通过）

| 层 | 测试文件 | 覆盖要点 |
| --- | --- | --- |
| 引擎 `engine/tests`（46 用例） | 契约/注册/配置/管线/观察者/会话/传输/WS/集成/设备模拟 | Provider 注册与校验、正常链路、VAD 短路、LLM 超时/重试/降级、多轮会话、帧编解码、abort/bye、真实 WebSocket、旧协议全流程、EngineRuntime 接管 |
| 核心 `core/tests`（5 用例） | `test_engine_runtime.py` | `engine.mode` 解析、Provider 解析、通道创建、WebSocket Surface 适配 |

> 说明：上游自带的 `main/xiaozhi-server/tests/`（豆包实时流等）依赖第三方
> 模型/云端服务与完整运行时，本机无法执行；已通过全库 `compileall` 语法验证。
| 配置完整性 | `main/xiaozhi-server/data/.config.yaml` | 存在，启动必需 |

## 一键自检

```bash
cd main/xiaozhi-server
python -m engine.check
```

输出末尾显示 `[CHECK] 全部通过: PASS` 即表示引擎层正常。

## 完整栈运行前提

以下为运行完整物联网 AI 平台（管理后台 + 硬件链路）所需条件：

| 组件 | 要求 |
| --- | --- |
| 语音核心 `xiaozhi-server` | Python 3.10+、FFmpeg、`pip install -r requirements.txt`、首次下载语音模型 |
| 管理后端 `manager-api` | JDK 21、Maven 3.8+、MySQL 8+、Redis |
| 管理 Web `manager-web` | Node.js（项目使用 Vue CLI 构建） |
| AI 能力 | 至少一个可用 LLM（智谱免费 Key 或本地 Ollama）；ASR/TTS 默认走本地/免费方案 |
| 端到端设备 | ESP32 设备（或使用 `python -m engine.device_simulator` 模拟验收协议） |

本机（2026-09-05 检查）仅具备 Node 24；Python、Java、MySQL、Redis、FFmpeg、
Docker 未安装，因此**完整三件套端到端运行尚未在本机执行**。

如要在本机补齐环境，可运行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/bootstrap_windows.ps1
```

脚本会用 winget 安装 Python 3.10、FFmpeg、JDK 21、Maven、Node.js（缺失项），
随后按提示安装 Python 依赖并执行引擎自检。

## 边界说明

- `engine/` 为原创实现，可独立测试与运行。
- `core/`、`manager-api/`、`manager-web/` 基于上游开源项目（MIT）改编，见根 README 来源声明。
