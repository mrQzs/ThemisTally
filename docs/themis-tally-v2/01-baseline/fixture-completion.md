# 01 缺字段 fixture 与扫描断言补齐

2026-09-26，在 `cd56775` 的模块 01 产物上补齐 acceptance 第 7 节第 24 项及 M-16。本文是本轮实现和命令结果记录；历史 `evidence/` 没有改写。本轮正式取证与验收结论由规划端的新验证记录绑定。

## 新增的两个单一故障样本

| fixture_id | 来源与唯一变化 | 锁定的旧行为 |
|---|---|---|
| `negative-legacy-contract-json-missing-task-id` | 来源 `legacy-contract-normalize-query-v1-json`，只删除 JSON 顶层 `task_id` 一行，配对 Markdown 不变 | `normalize_contract` 不补 `task_id`；旧 `validate_plan` 拒绝，CLI `validate` 退出 2 |
| `negative-legacy-events-ok-final-usage-missing-tokens` | 来源 `legacy-stub-events-ok`，只删除最终 assistant `message_end` 的 `usage` 中五个 token 字段，保留 `cost`、报告、全部其他事件和行尾 | 旧实现把该消息缺失 token 视作 0，仍累计其费用；总用量为 input=1000、output=200、cacheRead=0、cacheWrite=0、totalTokens=1200，估算费用 0.00086，`unpriced_messages=0`，`problems=[]` |

事件样本属于单一“token 字段缺失”故障：不是删除整个 usage，也不是删掉一整条消息。完整事件流的 `integrity=complete`，因为该样本没有截断或损坏流的 JSON 字节。两条都是 `synthetic_fixture`，不能证明真实 Pi 或厂商协议兼容。

两条新样本都能通过新入口的严格 JSON 文法检查。这不代表它们通过合同或厂商字段语义检查；新严格入口的判断继续单独保存在 `legacy-new-strict.json`。

生成器修订为 `codekit01-legacy-fixtures-v3`。先运行 `python tests/codekit01_legacy.py --write-derived`，再运行 `python tests/test_codekit01_fixtures.py --write`。前者只创建这两个新负例，`rewritten=[]`；不重取或重写已有 legacy/stub 原始 fixture。已有 manifest 条目及其中的 stub 条目副本、5 个派生协议负例同步更新生成器修订和 `expected_ref.sha256`。

## 测试与反测

新增 `MissingFieldLegacyTests` 两个方法：先因 fixture 未登记失败，再在生成后通过。合同断言独立核对只删除 `task_id`、旧实现不补默认值、拒绝与 CLI 退出码；事件断言独立核对只有一行改变、改变的消息身份、只缺五个 token 字段、保留费用与相邻消息，并锁定 `expects_settled=true/false/null` 三种投影。

`CredentialScanTests.test_fixture_files_contain_no_credential_shapes` 现在累计扫描器返回的白名单命中，并断言为空。为了验证原缺口，曾临时向一个合成 Markdown fixture 追加仓库已登记的 `DEMO_TOKEN_FOR_REVIEW` 标记：旧测试退出 0；加强断言后同一变体退出 1。每次均在 `finally` 恢复原字节并核对相等，未保存该变体。恢复后扫描测试通过。该反测只使用合成标记，没有读取真实凭据。

## Windows 局部复验结果

环境：CPython 3.12.10、Windows；所有下列命令设置 `PYTHONIOENCODING=utf-8`、`PYTHONDONTWRITEBYTECODE=1`。测试使用仓库已有受控临时 Git 仓库和 stub，没有调用真实模型。Linux、macOS 未运行。

| 命令/核对 | 结果 |
|---|---|
| `python tests/test_codekit01_fixtures.py MissingFieldLegacyTests CredentialScanTests -v` | 6 tests，全部通过，无 skip |
| `python tests/test_codekit01_fixtures.py -v` | 77 tests，全部通过，无 skip；首次完整复跑发现旧的负例类别计数仍是 157，更新为 159 后重跑通过 |
| `python tests/codekit01_legacy.py --check` | 40 checks，0 differ |
| `python tests/codekit01_legacy.py --check-stub-regen` | 10 checks，0 differ |
| 三份 expected 与 `cd56775` 逐既有 key 比较 | 全部既有 case 内容相同，只添加两个样本对应的记录 |
| 旧核心字节核对 | `scripts/pi_dispatch.py`、`tests/test_dispatch.py`、`tests/stub_pi.py`、`AGENTS.md` 与 `cd56775` 相同 |

## 计数与固定字节

| 集合 | 修改前 | 修改后 |
|---|---:|---:|
| manifest 条目 | 188 | 190 |
| fixture 文件（含 manifest） | 189 | 191 |
| legacy / negative / synthetic 条目 | 18 / 157 / 13 | 18 / 159 / 13 |
| 合同负例 / 事件负例 | 19 / 3 | 20 / 4 |
| 旧合同投影 case / 旧事件投影 case | 22 / 13 | 23 / 14 |
| 新严格 JSON / JSONL case | 18 / 13 | 19 / 14 |
| fixtures 测试方法 | 75 | 77 |

| 文件 | 字节数 | SHA-256 |
|---|---:|---|
| `negative/legacy-contracts/json-missing-task-id/normalize-query.v1.json` | 2320 | `a2275515b4b4138f51a3f907754ec4f94147494b099cf6450286637e6721bb7d` |
| `negative/legacy-events/ok-final-usage-missing-tokens/events.jsonl` | 5652 | `99f2255827e34c0ea087a9e470e9fc9be69aa9f4f085e503fa681d8219f39fd8` |
| `manifest.json` | 413719 | `60796c78161ed4a42db9ff5fcf535b50b2414f18245c49201782c6d2f3a418a7` |
| `expected/legacy-contracts.json` | 266589 | `cf74cf257099442212a84e9247de3354140c12a0e87b05acd412ede40fff5c3b` |
| `expected/legacy-events.json` | 115550 | `6bfad73dd52b02f70fc01bd27eb06f6dd3954a25b8514e5b3a3fb57568023759` |
| `expected/legacy-new-strict.json` | 16555 | `0ee530157f0dc2318e384f9707773992112ab250759544ff99cee40fa634e734` |

上表路径相对 `tests/fixtures/codekit01/`。旧实现仍固定为 `a4fa199` 的 `scripts/pi_dispatch.py`：SHA-256 `a00d693452b4345d6093efa9864de6e1b4cefacece867b617e68e6a8efce3ad4`。本轮没有改旧行为；token 缺失补 0 是为迁移登记的旧行为，不是新协议的推荐行为。
