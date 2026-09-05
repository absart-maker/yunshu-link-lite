# AI 引擎层（engine）设计文档

这是本项目 AI 语音核心的**原创引擎层**：不依赖任何厂商 SDK，以「能力契约 +
注册体系 + 异步编排状态机」组织语音交互链路，所有依赖仅是 Python 3.10+ 标准库。

## 设计目标

- **解耦**：上层只依赖稳定契约，不感知 ASR/LLM/TTS/VAD 的具体实现。
- **可插拔**：Provider 通过注册表以「分类.名称」定位，配置驱动实例化。
- **可观测**：流程全程产生事件，日志、指标、审计通过观察者挂载。
- **可测试**：参考实现（stubs）不联网、不加载模型，端到端链路一行命令可验证。
- **可演进**：通过 bridge 兼容既有 Provider，迁移成本可控。

## 目录结构

```text
engine/
├── contracts.py    能力契约与领域模型
├── registry.py     Provider 注册与实例化
├── config.py       引擎配置模型与校验
├── pipeline.py     异步编排状态机
├── session.py      会话与对话历史管理
├── transport.py    实时设备会话与帧协议
├── observers.py    事件总线与可观测组件
├── stubs.py        标准参考实现
├── demo.py         端到端演示入口
├── __main__.py     `python -m engine` 入口
├── bridge/         既有 Provider 兼容桥接层
├── device_simulator.py  模拟设备客户端
├── ws.py           极简 WebSocket 协议（标准库实现）
├── server.py       真实网络服务入口
└── tests/          单元测试
```

## 核心设计

### 能力契约（contracts.py）

四种能力以 `Protocol` 表达，实现方无需继承，只要满足方法签名即可：

- `SpeechToText.transcribe(audio, session_id) -> Transcript`
- `LanguageModel.stream_reply(messages, session_id) -> AsyncIterator[ReplyChunk]`
- `TextToSpeech.synthesize(text, session_id) -> AsyncIterator[SpeechChunk]`
- `VoiceActivityDetector.is_speech(audio) -> bool`

### 编排状态机（pipeline.py）

```text
  idle ──> listening ──> transcribing ──> thinking ──> speaking ──> done
                │                              │
                └── vad 静音 ──────────────> done（短路）
                上游任一步骤异常 ────────────────> failed
```

`AiPipeline.run_turn()` 负责阶段流转、超时控制、LLM 失败重试与降级，以及
事件发布；各阶段耗时写入 `TurnResult.metrics`。

### 会话层（session.py）

- `Conversation`：系统提示与多轮历史，自带条数上限裁剪与 token 估算。
- `Session`：设备连接粒度的会话状态。
- `SessionRegistry`：线程安全的会话注册表，支持上限与空闲回收。

`run_turn(audio, session_id, conversation=None)` 可传入对话对象，自动写入
本轮「用户输入 + 助手回复」，实现多轮上下文。

### 实时设备会话层（transport.py）

把「一条设备连接」抽象为三层，传输与业务完全解耦：

- `Frame` / `FrameCodec`：帧模型与编解码（默认 JSON 信封）。
- `AsyncTransport`：字节级传输协议（WebSocket / 串口 / TCP 均可实现）。
- `RealtimeDeviceChannel`：握手（`hello`）、音频流转、`abort`/`bye` 退出，
  把 `AiPipeline` 与 `SessionRegistry` 串成完整设备会话。

默认帧类型：`ready`、`listening`、`transcript`、`reply`、`audio`、
`error`、`aborted`、`bye`。

真实服务接线：`engine/bridge/websocket.py` 提供
`WebSocketTransport`，把一个 websockets 连接包装成 `AsyncTransport`，
再交给 `RealtimeServer.handle_connection()` 即可服务真实设备。

模拟设备演示：

```bash
python -m engine.device_simulator
```

真实 WebSocket 服务（无第三方依赖）：

```bash
# 终端 1：启动服务
python -m engine.server --port 8765

# 终端 2：客户端验收
python -m engine.server --client --port 8765
```

预期客户端输出：`ready -> listening -> transcript -> reply -> audio`。

## 使用

### 端到端演示（无需网络/模型）

```bash
cd main/xiaozhi-server
python -m engine.demo --config engine/examples/demo.json
```

或直接：

```bash
python -m engine
```

### 单元测试

```bash
python -m unittest discover -s engine/tests -t . -v
```

## 如何扩展一个 Provider

1. 实现对应契约（参考 `engine/stubs.py`）；
2. 调用注册表注册（或使用 `register_provider` 装饰器）；
3. 在配置中把 `{category}.name` 指向实现名；
4. 若配置有必填项，在注册时声明 `required_config`，失败会在启动前暴露。

## 与既有 Provider 的关系

现有的 `core/providers/{asr,llm,tts}/` 与连接层强耦合，本引擎通过
`engine/bridge/` 提供分类适配：

- `llm.py`：`LegacyLanguageModel` 包装旧式 `response()` 生成器。
- `tts.py`：`LegacyTextToSpeech` / `StreamingTextToSpeech` 包装同步与流式合成。
- `vad.py`：`LegacyVoiceActivityDetector` 包装旧式 `is_vad()`。
- `asr.py`：`FunctionSpeechToText` 包装任意「音频字节→文本」函数；
  `LegacySpeechToText` 通过连接代理适配旧式 Receiver。

### 旧服务接线（integration.py）

把旧配置与旧 WebSocket 协议接到新引擎：

- `build_pipeline_from_config(config)`：按 `selected_module` 装配引擎；
  未注册实现自动回退到标准参考实现并返回警告。
- `LegacyProtocolAdapter`：旧协议「JSON 控制消息 + 二进制音频」与
  引擎 `Frame` 双向转换。
- `LegacySessionChannel`：用旧协议驱动完整一轮交互
  （`hello → audio → stt/llm/音频 → bye`）。
- `EngineRuntime`：直接托管在标准库 WebSocket 服务上，服务旧设备协议。

```bash
python -m unittest engine.tests.test_integration -v
```

### 一键切换旧服务到新引擎（core/engine_runtime.py）

在 `data/.config.yaml` 增加：

```yaml
engine:
  mode: auto           # legacy（默认）| engine | auto
  # 显式指定引擎 Provider（可选，未配置时读取 selected_module）
  providers:
    asr: { name: echo }
    llm: { name: rule }
    tts: { name: palette }
    vad: { name: always_voice }
```

- `legacy`：完全保持原有行为（默认，零改动）。
- `engine`：强制接管连接；Provider 无法完整解析时拒绝连接并记录错误。
- `auto`：引擎可完整解析则接管，否则记录警告并回退旧处理器。

接入点：[core/websocket_server.py](../../core/websocket_server.py) 已内置分支，
设备无需改动。

### 接入真实服务的路径

1. 用 `data/.config.yaml` 的 `selected_module` 找到实际选中的 Provider；
2. 通过 `engine/bridge/` 的对应适配器包装为契约对象；
3. 构造 `AiPipeline`，并挂载 `SessionRegistry`；
4. 用 `RealtimeServer.handle_connection(transport)` 接入任意传输实现；
5. 设备侧按 `ready → hello → audio → reply/audio → bye` 进行交互；
6. 现有 WebSocket 通道使用 `WebSocketTransport` 包装后即可替换原连接层逻辑。
