# 13 Observer 协议离线复审

状态：`OFFLINE_ACCEPTED_WITH_BOUNDARY`

## 范围

本复审覆盖 `ObserverRequest`、`ObserverSuggestion` 和 `ObserverOutput` 的离线结构与引用闭包校验，位置为 `scripts/codekit/observer_protocol.py`。协议使用既有 `ResourceRef` 和严格 JSON 解码器；请求、输出、建议均为闭合对象。

已验证的边界：

- 请求固定事件起止游标、brief 引用、来源集合、输出上限、profile/environment/budget 引用、时限和重试上限；
- facts、hypotheses、risks、open_questions、suggested_next_actions、omitted 分开建模；事实、推断和建议必须分别携带输入内来源；
- 输出只能引用请求中的 brief/source refs，游标和 brief 必须与请求相同；可选 trusted registry 可进一步核对引用存在性；
- 未知字段、重复/越界来源、缺失事实来源、游标漂移和严格 JSON 重复键均拒绝；
- `PASS`、批准、授权、发布等伪结论不会进入摘要字段；输出 status 只允许 `OK/PARTIAL/DEGRADED/REJECTED`，不授予任何核心状态；
- 只提供纯校验、规范化和摘要 digest 函数；`validate_observer_source_ref` 可对调用方传入的精确 UTF-8 bytes 重算 SHA-256，但不会打开路径、调用模型、provider、预算账本或外部连接器。

## 验证证据

```text
PYTHONPATH=scripts python -m unittest tests/test_13_observer_protocol.py -v
Ran 7 protocol tests ... OK（另有 9 项 offline runtime tests；两组共 16 项）
python -m compileall -q scripts/codekit/observer_protocol.py
```

Schemas：`schemas/observer-request-v1.schema.json`、`schemas/observer-output-v1.schema.json` 已解析为有效 JSON。Windows Python 未安装 `jsonschema`，Draft 2020-12 Schema 语义校验需在既有 WSL Python 3.12 环境执行。

## 未运行/阻塞

真实摘要模型、provider/CLI、Pi、预算预留、通知宿主、跨平台只读隔离、外部 09/10 连接器和生产摘要调用均为 `NOT_RUN/BLOCKED`。本复审不能证明阅读价值、token 节省、真实费用或操作系统强制只读；协议引用存在性只在调用方传入受信 registry 时检查，模块不会自行打开引用路径。
