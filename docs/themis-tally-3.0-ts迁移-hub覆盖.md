# 第 ⑤ 步的覆盖审计：tests/test_kit_hub.py 的场景对到 TS 契约

迁移计划第 ⑤ 步的出口条件（v1.6，themistally-15 提出）：297 个场景逐个对到 TS 契约，记成 COVERED、PARTIAL、MISSING；切换之前 MISSING 清零或写明理由。每片交付时补自己那一块。

- **COVERED**：同一场景两边各跑：Python 与 TS（Node、Bun）在同样的输入上逐字比，输入取自用例本身（照步骤搭出的状态，或 Python 探针 hub.samples 从用例里取出的参数）。
- **PARTIAL**：用例里的一部分已覆盖，其余归后面的片，写明归哪一片。
- **MISSING**：还没有对应的契约。

随机对照（hub-state.compare 的“随机”几条）不算进某个用例的覆盖，只当额外的保护。

## ⑤a 常量、信件、状态机守卫

| 用例 | 行 | 状态 | TS 契约 |
|---|---|---|---|
| `test_letter_round_trip_keeps_multiline_fields` | 87 | COVERED | hub-state.compare「信件」：照搬往返 |
| `test_letter_shape_errors（4 个参数）` | 104 | COVERED | hub-state.compare「信件」：hub.samples 从用例取出、lambda 在 Python 一侧执行 |
| `test_letter_body_limit_and_audit_verdict` | 112 | COVERED | hub-state.compare「信件」：照搬九种组合 |
| `test_guard_owner_and_routing_rules` | 150 | COVERED | hub-state.compare「守卫：开工、返工、通过」：照步骤 |
| `test_guard_plan_contract_gate_and_jev_starts` | 162 | COVERED | 同上 |
| `test_guard_audit_pre_needs_locked_baseline_and_jev` | 178 | COVERED | 同上 |
| `test_guard_exec_needs_passing_first_review_on_the_same_bytes` | 190 | COVERED | 同上 |
| `test_guard_short_circuit_after_execution` | 204 | COVERED | 同上 |
| `test_guard_rework_targets` | 225 | COVERED | 同上 |
| `test_final_review_can_return_to_the_contract_and_to_the_post_gate` | 248 | COVERED | 同上 |
| `test_gate_hotfix_needs_the_executors_evidence_or_a_final_review_return` | 290 | COVERED | hub-state.compare「守卫：热修补……」：照步骤 |
| `test_guard_final_pass_needs_final_review` | 1239 | COVERED | hub-state.compare「守卫：开工、返工、通过」 |
| `test_guard_final_pass_waits_for_a_failed_rehearsal_of_this_candidate` | 1248 | COVERED | 同上（含 allowed_moves） |
| `test_upstream_redelivery_invalidates_only_dependents` | 1264 | COVERED | 同上（invalidate_after 两次） |
| `test_allowed_moves_lists_only_passing_letters` | 1281 | COVERED | 同上 |
| `test_legacy_task_without_external_facts_is_not_blocked` | 1807 | PARTIAL | guard 一句在「守卫：热修补……」；external_facts_section 归 ⑤d |
| `test_audit_may_return_several_stages_and_the_upstream_one_goes_first` | 5223 | PARTIAL | letter_errors、return_stages、guard、hotfix_reason 都在「守卫：热修补……」；最后两句核对提示词（ROLE_EXTRA_OUTPUT、worker.md）归 ⑤d |
| `test_owner_ordered_gate_rework_is_a_hotfix_and_holds_the_executor_back` | 5460 | COVERED | hub-state.compare「守卫：热修补……」 |
| `test_a_gate_claim_opens_the_hotfix_and_holds_the_executor_until_the_gate_redelivers` | 6604 | COVERED | 同上 |
| `test_the_schema_subset_validator（34 个参数）` | 7231 | COVERED | hub-state.compare「schema 子集」：hub.samples 取 SCHEMA_SAMPLES |
| `test_role_schemas_only_use_the_subset_and_match_the_kernel` | 7235 | COVERED | 同上：五份岗位 schema 加四种子集外写法 |
| `test_routine_letters_map_to_the_next_step（11 个参数）` | 7480 | COVERED | hub-state.compare「信件」：hub.samples 用用例的 routine_letter 渲染 |
| `test_exceptions_go_to_the_coordinator（7 个参数）` | 7495 | COVERED | 同上 |
| `test_routine_briefs_quote_each_path_on_its_own` | 7673 | COVERED | hub-state.compare「守卫：开工、返工、通过」：engine_env 只提供仓库与状态，直接调 |
| `test_downstream_notes_ride_along_to_every_later_turn` | 7729 | PARTIAL | upstream_notes 在随机对照里；进回合输入（turn_prompt）归 ⑤d |
| `test_stage_reworks_are_capped` | 1564 | PARTIAL | 返工上限的 guard 与状态表在随机对照里；经 Engine 的场景归 ⑤i |

⑤a 里的变异（ts/mutations/hub-a.ts.json）30 条（含 base 的 purePathRelativePosix 两条），抓住 27 条，3 条照实测标为等价：字段名前的空白（已知字段名里没有空白）、冒号后的制表符（值随后整体 strip）、布尔不算数字（JS 的布尔本来就不是数字）。

## ⑤b 信箱、账本与状态

做法（themistally-15 提出）：每一步推进状态的操作本身就是一次比较过的请求。同一份步骤脚本交给三套实现，各在一个新信箱上从头跑，每一步的结果与最后落盘的文件都与 Python 逐字比（账本的时间、内核信件的随机编号与随之变的 sha256 换成占位符）。脚本里的 set、del、save_dict、write_file 是输入，照搬 pytest 用例对状态与文件的直接改动，不拿 TS 的输出去推进下一步。混跑用例里一套实现停在两步之间、另一套插进来，两边都是被比的一方。

| 用例 | 行 | 状态 | TS 契约 |
|---|---|---|---|
| `test_delivery_never_overwrites_and_take_moves_to_cur` | 129 | COVERED | hub-mailbox「B1」：照搬；new 里的排序另有「B9」（NTFS 列目录的次序与 Python 的排序不同的名字） |
| `test_rewritten_reports_and_briefs_keep_their_previous_versions` | 1175 | COVERED | hub-mailbox「B8」：照搬三轮；序号往后排另有「B5」 |
| `test_state_saves_merge_by_task_and_key` | 3913 | COVERED | hub-mailbox「B2」：照步骤（two_task_hub 的两个主任务、手搭的 dict）；另有「B10」（存过之后读出来时的样子跟着更新）、「C1」（两套实现交错着存） |
| `test_turn_end_keeps_the_sessions_other_tasks_wrote` | 3950 | COVERED | hub-mailbox「B3」：照搬；「C3」「C5」加并发 |
| `test_file_lock_keeps_other_holders_out` | 3961 | COVERED | filelock.contract 的 F1、F2（第 ④ 步）；hub-mailbox「C5」：Python 拿着 .state.lock、.agents.lock 时，各套实现的写都等它放开 |
| `test_state_writes_and_reads_wait_out_a_sharing_violation` | 6046 | COVERED | hub-mailbox「C4」：用真的独占打开代替 monkeypatch（短的等过去，长的读报“读不出”、写报 PermissionError，不留临时文件），备份特权启用、停用两种状态都跑；启用时 TS 的读是已知差异（迁移计划第 10 节）。missing.txt 一句在 locks.contract，新信箱一句在「B7」 |
| `test_a_rate_limited_worker_turn_is_held_and_resumed` | 1857 | PARTIAL | 扣信（额度限制写信给站主、阶段标 paused）、没到点不放、到点放回且阶段回到 assigned 在「B4」，到点的边界在「B11」；经 Engine 的回合归 ⑤i |
| `test_held_letters_are_dropped_when_the_stage_was_restarted_meanwhile` | 1892 | PARTIAL | 阶段变了就丢掉、信留在 cur、记 letters.dropped 不记 letters.released 在「B4」；经 Engine 的回合归 ⑤i |
| `test_exec_waits_for_the_landing_lock_by_holding_its_letter` | 5356 | PARTIAL | 内核自己等（带原因）不写信给站主在「B4」；执行端代办与落地锁归 ⑤g、⑤h |
| `test_task_runner_only_takes_its_own_task_letters` | 3986 | PARTIAL | letter_main 在「B5」；Engine.next_job、tasks_with_work 归 ⑤i |

⑤b 里的变异（ts/mutations/hub-b.ts.json）21 条，全部抓住。第一轮 20 条漏掉 5 条（存完不更新读出来时的样子、会话记录不加锁、new 里的信不排序、到点的边界、读不出时不报错），补了 B7 的只有空白的文件、B9 到 B11、C4 的备份特权停用状态与 C5 之后都抓住；另加“三方合并不加锁”一条。

其余场景随各片补（⑤c 到 ⑤j）。
