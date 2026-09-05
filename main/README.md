# 主干结构与技术说明

本目录是精简改编版的核心三件套，技术栈与职责如下。

## 1. `xiaozhi-server`（Python 语音核心）

异步实时 AI 管线，逻辑集中在 `core/`：

- `core/connection.py`：连接级编排，维护每个设备连接的对话状态与模块实例。
- `core/websocket_server.py`、`core/http_server.py`：WebSocket 语音通道与 HTTP / Vision 接口。
- `core/providers/`：可插拔能力抽象，包含 `asr`、`llm`、`tts`、`vad`、`vllm`、`memory`、
  `intent`、`s2s`、`tools`，通过 `data/.config.yaml` 的 `selected_module` 热切换。
- `core/handle/`：协议消息处理（音频接收/发送、文本消息、意图、上报、OTA 等）。
- `plugins_func/functions/`：工具插件（天气、新闻、时间、音乐、HomeAssistant、RAG 检索、
  Web 搜索、设备调用等），启动时自动注册。
- 通信入口：WebSocket `:8000`，HTTP/Vision `:8003`。

### 1.1 原创 AI 引擎层（`engine/`）

`engine/` 是面向语音交互链路的原创核心，提供能力契约、Provider 注册体系、
JSON 配置校验与异步编排状态机，依赖仅为 Python 标准库：

- `contracts.py`：`SpeechToText` / `LanguageModel` / `TextToSpeech` /
  `VoiceActivityDetector` 四类契约。
- `pipeline.py`：`AiPipeline` 状态机，负责阶段流转、超时、LLM 重试/降级与事件发布。
- `session.py`：`Conversation` / `Session` / `SessionRegistry`，多轮上下文与会话生命周期管理。
- `registry.py` / `config.py`：配置驱动的 Provider 定位、实例化与启动前校验。
- `observers.py`：事件总线、结构化日志与指标采集。
- `stubs.py` / `demo.py`：无外部依赖的参考实现与端到端演示。
- `bridge/`：对既有 Provider 的兼容桥接（LLM / TTS / VAD / ASR）。

验证方式：

```bash
cd main/xiaozhi-server
python -m engine
python -m unittest discover -s engine/tests -t . -v
```

设计细节见 [engine/README.md](xiaozhi-server/engine/README.md)。

### 1.2 旧服务引擎开关

`core/engine_runtime.py` 提供 `engine.mode` 三档开关（`legacy` / `engine` /
`auto`），`core/websocket_server.py` 已内置分支：默认 `legacy` 保持原行为；
设置 `engine.mode: auto` 可在引擎完整解析 Provider 时自动接管，否则回退
旧处理器，设备协议无需改动。详见 [engine/README.md](xiaozhi-server/engine/README.md)。

## 2. `manager-api`（Java 管理后端）

Spring Boot 3.4 + MyBatis-Plus + MySQL + Redis + Shiro 鉴权，职责：

- 用户、设备、智能体、模型、音色、声纹、知识库、OTA 等实体管理。
- 配置下发与鉴权，提供 OpenAPI（Knife4j）文档，服务地址 `:8002`。

主要控制器：`AgentController`、`DeviceController`、`ModelController`、`KnowledgeBaseController`、
`VoicePrintController`、`OTAController`、`LoginController` 等，均在
`src/main/java` 下按模块组织。

## 3. `manager-web`（Vue 管理控制台）

Vue 2 + Element UI，提供设备、智能体/角色、模型、知识库、声纹、音色、模板、OTA、用户与参数
等管理页面。开发服务 `:8001`，接口代理到 `:8002`。

## 学习路径建议

1. 先读 `xiaozhi-server/core/`：理解连接编排与 Provider 插拔机制。
2. 再读 `manager-api` 的一个控制器 + Service：理解 Spring Boot 工程组织。
3. 最后在 `plugins_func/functions/` 写一个自己的工具插件，接一点增量。
4. 没有硬件时，可用 WebSocket 客户端脚本模拟设备，走通语音协议。

更多部署与集成说明见根目录 `docs/`。
