# 功能文档索引

本目录保留的是部署与功能集成所需的说明文档（非项目介绍类），按用途分类如下。

## 部署与运行

| 文档 | 内容 |
| --- | --- |
| `Deployment.md` | 标准部署流程 |
| `Deployment_all.md` | 全模块部署流程 |
| `docker-build.md` | Docker 镜像构建 |
| `firmware-build.md` / `firmware-setting.md` | 固件编译与设置 |

`docker/` 下的 `nginx.conf`、`start.sh` 为容器运行必需配置，请勿删除。

## AI 能力集成

- 语音识别/合成：`doubao-realtime-s2s-integration.md`、`fish-speech-integration.md`、
  `index-stream-integration.md`、`paddlespeech-deploy.md`、`huoshan-streamTTS-voice-cloning.md`
- 模型与记忆：`context-provider-integration.md`、`powermem-integration.md`
- 知识库：`ragflow-integration.md`
- 声纹：`voiceprint-integration.md`

## 工具与设备

- MCP：`mcp-endpoint-integration.md`、`mcp-endpoint-enable.md`、`mcp-get-device-info.md`、
  `mcp-vision-integration.md`
- 设备：`device-call-guide.md`、`mqtt-gateway-integration.md`、`homeassistant-integration.md`
- 升级与运维：`ota-upgrade-guide.md`、`dev-ops-integration.md`、`performance_tester.md`
- 插件：`weather-integration.md`、`web-search-integration.md`、`newsnow_plugin_config.md`
- 短信：`ali-sms-integration.md`

> 注：以上文档出自上游项目，部分内容会引用已移除的移动端或数字人模块；使用时只参考与当前
> 三件套（`xiaozhi-server` / `manager-api` / `manager-web`）相关的部分。
