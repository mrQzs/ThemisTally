# 第 ⑤ 步的覆盖审计：tests/test_kit_hub.py 的场景对到 TS 契约

迁移计划第 ⑤ 步的出口条件（v1.6，themistally-15 提出）：298 个场景逐个对到 TS 契约，记成 COVERED、PARTIAL、MISSING；切换之前 MISSING 清零或写明理由。每片交付时补自己那一块。

- **COVERED**：同一场景两边各跑：Python 与 TS（Node、Bun）在同样的输入上逐字比，输入取自用例本身（照步骤搭出的状态，或 Python 探针 hub.samples 从用例里取出的参数）。
- **PARTIAL**：用例里的一部分已覆盖，其余归后面的片，写明归哪一片。
- **MISSING**：还没有对应的契约。

同一条用例出现在几节里时，以后面那节为准（例如 ⑤e1b 表里记成漂移的 7 条、⑤c 记 PARTIAL 的 worker_env 那条，⑤e2a 一节改记了新的状态）。

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
| `test_legacy_task_without_external_facts_is_not_blocked` | 1807 | COVERED | guard 一句在「守卫：热修补……」；external_facts_section 在 hub-prompt（⑤d1）的记下的调用 |
| `test_audit_may_return_several_stages_and_the_upstream_one_goes_first` | 5227 | PARTIAL | letter_errors、return_stages、guard、hotfix_reason 都在「守卫：热修补……」；最后两句核对提示词（ROLE_EXTRA_OUTPUT、worker.md）归 ⑤d |
| `test_owner_ordered_gate_rework_is_a_hotfix_and_holds_the_executor_back` | 5464 | COVERED | hub-state.compare「守卫：热修补……」 |
| `test_a_gate_claim_opens_the_hotfix_and_holds_the_executor_until_the_gate_redelivers` | 6608 | COVERED | 同上 |
| `test_the_schema_subset_validator（34 个参数）` | 7235 | COVERED | hub-state.compare「schema 子集」：hub.samples 取 SCHEMA_SAMPLES |
| `test_role_schemas_only_use_the_subset_and_match_the_kernel` | 7239 | COVERED | 同上：五份岗位 schema 加四种子集外写法 |
| `test_routine_letters_map_to_the_next_step（11 个参数）` | 7484 | COVERED | hub-state.compare「信件」：hub.samples 用用例的 routine_letter 渲染 |
| `test_exceptions_go_to_the_coordinator（7 个参数）` | 7499 | COVERED | 同上 |
| `test_routine_briefs_quote_each_path_on_its_own` | 7677 | COVERED | hub-state.compare「守卫：开工、返工、通过」：engine_env 只提供仓库与状态，直接调 |
| `test_downstream_notes_ride_along_to_every_later_turn` | 7733 | COVERED | upstream_notes 在随机对照里；进回合输入（turn_prompt）与 letter_from_output 在 hub-prompt（⑤d1）的记下的调用 |
| `test_stage_reworks_are_capped` | 1564 | PARTIAL | 返工上限的 guard 与状态表在随机对照里；经 Engine 的场景归 ⑤i |

⑤a 里的变异（ts/mutations/hub-a.ts.json）30 条（含 base 的 purePathRelativePosix 两条），抓住 27 条，3 条照实测标为等价：字段名前的空白（已知字段名里没有空白）、冒号后的制表符（值随后整体 strip）、布尔不算数字（JS 的布尔本来就不是数字）。

## ⑤b 信箱、账本与状态

做法（themistally-15 提出）：每一步推进状态的操作本身就是一次比较过的请求。同一份步骤脚本交给三套实现，各在一个新信箱上从头跑，每一步的结果与最后落盘的文件都与 Python 逐字比（账本的时间、内核信件的随机编号与随之变的 sha256 换成占位符）。脚本里的 set、del、save_dict、write_file 是输入，照搬 pytest 用例对状态与文件的直接改动，不拿 TS 的输出去推进下一步。混跑用例里一套实现停在两步之间、另一套插进来，两边都是被比的一方。

| 用例 | 行 | 状态 | TS 契约 |
|---|---|---|---|
| `test_delivery_never_overwrites_and_take_moves_to_cur` | 129 | COVERED | hub-mailbox「B1」：照搬；new 里的排序另有「B9」（NTFS 列目录的次序与 Python 的排序不同的名字） |
| `test_rewritten_reports_and_briefs_keep_their_previous_versions` | 1175 | COVERED | hub-mailbox「B8」：照搬三轮；序号往后排另有「B5」 |
| `test_state_saves_merge_by_task_and_key` | 3912 | COVERED | hub-mailbox「B2」：照步骤（two_task_hub 的两个主任务、手搭的 dict）；另有「B10」（存过之后读出来时的样子跟着更新）、「C1」（两套实现交错着存） |
| `test_turn_end_keeps_the_sessions_other_tasks_wrote` | 3949 | COVERED | hub-mailbox「B3」：照搬；「C3」「C5」加并发 |
| `test_file_lock_keeps_other_holders_out` | 3960 | COVERED | filelock.contract 的 F1、F2（第 ④ 步）；hub-mailbox「C5」：Python 拿着 .state.lock、.agents.lock 时，各套实现的写都等它放开 |
| `test_state_writes_and_reads_wait_out_a_sharing_violation` | 6050 | COVERED | hub-mailbox「C4」：用真的独占打开代替 monkeypatch（短的等过去，长的读报“读不出”、写报 PermissionError，不留临时文件），备份特权启用、停用两种状态都跑；启用时 TS 的读是已知差异（迁移计划第 10 节）。missing.txt 一句在 locks.contract，新信箱一句在「B7」 |
| `test_a_rate_limited_worker_turn_is_held_and_resumed` | 1857 | PARTIAL | 扣信（额度限制写信给站主、阶段标 paused）、没到点不放、到点放回且阶段回到 assigned 在「B4」，到点的边界在「B11」；经 Engine 的回合归 ⑤i |
| `test_held_letters_are_dropped_when_the_stage_was_restarted_meanwhile` | 1892 | PARTIAL | 阶段变了就丢掉、信留在 cur、记 letters.dropped 不记 letters.released 在「B4」；经 Engine 的回合归 ⑤i |
| `test_exec_waits_for_the_landing_lock_by_holding_its_letter` | 5360 | PARTIAL | 内核自己等（带原因）不写信给站主在「B4」；执行端代办与落地锁归 ⑤g、⑤h |
| `test_task_runner_only_takes_its_own_task_letters` | 3985 | PARTIAL | letter_main 在「B5」；Engine.next_job、tasks_with_work 归 ⑤i |

⑤b 里的变异（ts/mutations/hub-b.ts.json）21 条，全部抓住。第一轮 20 条漏掉 5 条（存完不更新读出来时的样子、会话记录不加锁、new 里的信不排序、到点的边界、读不出时不报错），补了 B7 的只有空白的文件、B9 到 B11、C4 的备份特权停用状态与 C5 之后都抓住；另加“三方合并不加锁”一条。

## ⑤c 回合审计

做法：样例只有 pytest 这一个来源。Python 探针 hub.audit_samples 跑下表里不经 Engine 的用例，记下它们对审计函数的每一次顶层调用（共 94 次；tmp_path 用解析过的长路径，与 pytest 一样），契约 hub-audit「pytest 的场景」把这些调用原样交给三边重放，逐字比整份结果，比 pytest 自己的断言严。另有 guard.ts 的三方对照、按种子改坏的事件流、手写的边界与会话文件。tests/test_path_forms.py 第 133 轮新加的两条（次序、16 个散列种子）只在 Python 一侧，TS 的 path_forms 由契约逐字比。

| 用例 | 行 | 状态 | TS 契约 |
|---|---|---|---|
| `test_claude_audit_rejects_advisor_and_tools_outside_the_allowlist` | 1303 | COVERED | hub-audit：记下的调用三边重放 |
| `test_refused_calls_outside_the_allowlist_only_warn` | 1314 | COVERED | hub-audit：同上 |
| `test_claude_audit_checks_init_and_model` | 1335 | COVERED | hub-audit：同上 |
| `test_pi_audit_rejects_tools_and_records_effective_level` | 1348 | COVERED | hub-audit：同上 |
| `test_audits_name_model_api_errors_instead_of_blaming_the_output` | 1368 | COVERED | hub-audit：同上 |
| `test_pi_refused_calls_outside_the_allowlist_only_warn` | 1390 | COVERED | hub-audit：同上 |
| `test_audit_reads_when_a_rate_limit_lifts` | 2348 | COVERED | hub-audit：同上 |
| `test_claude_path_rule_uses_the_absolute_form` | 3848 | COVERED | hub-audit：同上；「手写的边界」另有 8.3 短名、大小写写错、相对路径 |
| `test_the_guard_extension_judges_every_call_like_the_audit` | 5889 | COVERED | hub-audit：同上；「guard.ts 的三方对照」用它的 25 次调用加随机的字典参数，guard.ts 在 Node 与 Bun 下各跑一次 |
| `test_calls_the_guard_blocked_are_warnings_not_violations` | 5914 | COVERED | hub-audit：记下的调用三边重放 |
| `test_claude_workers_are_audited_for_the_main_worktree_too` | 5964 | COVERED | hub-audit：同上 |
| `test_u2028_in_a_tool_call_cannot_hide_it_from_the_audit` | 6867 | COVERED | hub-audit：同上；「逐行解析」另有各种断行字符 |
| `test_unreadable_stream_lines_are_violations` | 6894 | COVERED | hub-audit：同上 |
| `test_the_pi_audit_takes_the_last_accepted_deliver` | 7285 | COVERED | hub-audit：同上 |
| `test_unreadable_lines_are_not_counted_as_unreadable_deliveries` | 7918 | COVERED | hub-audit：同上（第 133 轮新加） |
| `test_pi_workers_load_the_guard_with_the_kernel_roots` | 5946 | COVERED | hub-audit：审计、guard_config、path_forms 在记下的调用；两次 TurnRunner.run 在 hub-turn（⑤d2）的采样重放：第一次没有覆盖值（带守卫的参数与 THEMIS_GUARD 逐字比），第二次照记下的 DELIVERY_SHA256 的 guard.ts（全零） |
| `test_a_session_cut_short_mid_tool_call_is_not_continued` | 2226 | COVERED | hub-audit：session_cut_short 的判法在「会话文件」；经 TurnRunner 的三次回合在 hub-turn（⑤d2）的采样重放 |
| `test_turn_cost_is_this_turn_not_the_session_total` | 3692 | COVERED | hub-audit：turn_cost_usd 在「手写的边界」；TurnRunner 记会话累计在 hub-turn（⑤d2）的采样重放 |
| `test_claude_workers_read_the_inputs_and_write_only_their_worktree` | 3798 | COVERED | hub-audit：claude_path_rule 在「手写的边界」；两次 TurnRunner.run 在 hub-turn（⑤d2）的采样重放，照调用当时记下的覆盖值：名册的 gate-sonnet、audit-sonnet 换成用例的 CLAUDE_GATE、CLAUDE_AUDIT |
| `test_pi_workers_may_not_write_outside_their_worktree` | 5856 | COVERED | hub-audit：越界的判定在「guard.ts 的三方对照」与随机调用；经 TurnRunner 的回合在 hub-turn（⑤d2）的采样重放 |
| `test_ledger_session_and_decision_records_with_u2028_are_read_back` | 6907 | PARTIAL | hub-audit：claude_session_effort 那份会话文件原样在「会话文件」；exec_metrics 归 ⑤j；decisions.read_records 在 ④ 的契约里 |
| `test_a_deliver_that_quotes_the_main_worktree_is_not_a_reach` | 7303 | COVERED | hub-audit：用例只调 audit_pi_stream（不经 TurnRunner，⑤c 起初记错了），⑤d2 时加进 hub-audit 的采样清单，记下的调用三边重放 |

⑤c 里的变异（ts/mutations/hub-c.ts.json）37 条，抓住 36，1 条照实测标为等价（C25：main 已经 normcase，依赖目录名是小写 ASCII、按段拼接，再 normcase 一次不改任何字）。第一轮漏掉 4 条：补了“说明截到 200 个字”“1 与 1.0 在集合里是同一个”“dict() 把长度为 2 的字符串当成一对”三例；截断那条补了之后仍漏，原因是契约的临时目录带 8.3 短名，path_forms 经 resolve 得到长名，命令里写短名对不上、根本没被判违规。主工作区改按长名搭之后抓住，短名的写法留作一种“不该被判违规”的写法。

## ⑤d 回合启动与输入

### ⑤d1 提示词与交差核对

做法：照 ⑤c，Python 探针 hub.audit_samples 跑下表的用例与 ⑤a 一节的 1807、7729（共 34 条），记下它们对回合输入与交差核对函数的每一次顶层调用（Hub 记成仓库路径），契约 hub-prompt 交给 Python、Node、Bun 在同一份文件上重放、逐字比。采样照 pytest 先搭两个 autouse 夹具（test_kit_hub 的 pi_knows_every_flag、conftest 的 python_kernel_impl；⑤c 起初没搭，那时采的用例不受影响，⑤c 的契约照旧全过）与用例自己的 engine_env。用例里改过的内核全局（模板目录、HERE、read_text 的替身）重放时已经撤销：要点在那上面的三条另有手写的对照（两边设同一个值），记 COVERED；其余照实记 PARTIAL。经 Engine 的用例里 turn_prompt 是按模块名取的，照样记下，正好带来真实的主任务状态形状。记录器另记下调用当时的结果（themistally-15 提出），契约先核对 Python 重放与它：对不上的用例 5 条（下表注明），只有另有手写对照的两条记 COVERED；⑤c 用同一个采样，94 次调用全部对上，⑤c 一节的数字不变。

| 用例 | 行 | 状态 | TS 契约 |
|---|---|---|---|
| `test_planner_sees_the_transitional_gate_assertions` | 599 | COVERED | hub-prompt：记下的调用三边重放；「过渡断言」另有生成的门禁测试与前端测试 |
| `test_planner_sees_the_transitional_frontend_cases` | 624 | COVERED | hub-prompt：同上（E6 的三支） |
| `test_planner_sizes_the_slice_against_one_attempt` | 647 | COVERED | hub-prompt：记下的调用 |
| `test_gate_rules_keep_the_regression_tests_valid_after_integration` | 654 | COVERED | hub-prompt：同上 |
| `test_role_prompt_only_renders_the_workers_own_duties` | 3619 | COVERED | hub-prompt：同上；「手写的对照」另有临时模板目录里的角色段 |
| `test_engineering_rules_from_committed_agents_md_reach_the_pi_roles` | 3631 | COVERED | 用例改 HERE 指到临时仓库（重放时已撤销，当时的结果与重放对不上）：「手写的对照」两边设同一个内核仓库（已提交与没提交、在末尾、标题后没有换行、不是仓库） |
| `test_the_committed_agents_md_has_the_engineering_rules` | 3653 | COVERED | hub-prompt：记下的调用（真的内核仓库） |
| `test_template_read_waits_out_a_file_being_replaced` | 5134 | COVERED | 用例换掉 read_text 与 sleep（重放时已撤销，当时的结果与重放对不上）：「手写的对照」用真的文件——先是空的、0.3 秒后有内容，一直是空的、不存在的报 HubError |
| `test_worker_prompts_state_the_turn_time_limit` | 6660 | COVERED | hub-prompt：记下的调用；随机对照另有没有时限的岗位 |
| `test_the_prompt_says_how_to_hand_in` | 7836 | COVERED | hub-prompt：记下的调用 |
| `test_unreadable_lines_are_not_counted_as_unreadable_deliveries` | 7918 | COVERED | ⑤c 已覆盖审计一半；interface_problem 在 hub-prompt 的记下的调用 |
| `test_contract_delivery_is_refused_when_the_budget_leaves_one_attempt` | 574 | PARTIAL | turn_prompt 的预算一行在记下的调用；accept_contract 归 ⑤e |
| `test_kernel_writes_the_contract_version_and_base_it_assigns` | 1441 | PARTIAL | next_contract_version 在「回合输入的小件」；accept_contract 改写合同归 ⑤e |
| `test_contract_runs_the_earlier_gates_as_regression_checks` | 1472 | PARTIAL | regression_gates 与合同端的回合输入在记下的调用；contract_requirements 归 ⑤e |
| `test_decisions_are_attached_to_the_contract_and_shown_to_the_contract_writer` | 6486 | PARTIAL | 站主决定进合同端的回合输入在记下的调用；附进合同归 ⑤e |
| `test_gate_post_judges_mutations_from_the_record` | 740 | PARTIAL | 审核端的存档一节在记下的调用；变异判定归 ⑤f |
| `test_gate_post_checks_the_anchors_before_mutating` | 795 | PARTIAL | 同上；锚点核对归 ⑤f |
| `test_mutations_must_cover_the_changed_files` | 1531 | PARTIAL | 同上；覆盖核对归 ⑤f |
| `test_new_attempt_gate_post_starts_from_the_previous_whitebox` | 5295 | PARTIAL | turn_prompt 的“新的 attempt”一行在记下的调用；seed_whitebox 归 ⑤f |
| `test_worker_env_drops_the_decision_key_and_host_session_vars` | 3893 | PARTIAL | worker_env 在「手写的对照」（设了假 key 的环境，只比名字）；kernel_env 归 ⑤f |
| `test_planner_may_only_run_npm_view` | 3827 | COVERED | role_prompt 在 hub-prompt 的记下的调用；claude 工人的 --allowedTools 在 hub-turn（⑤d2）的采样重放 |
| `test_an_audit_turn_hands_in_through_deliver` | 7348 | COVERED | letter_from_output、role_schema 在 hub-prompt 的记下的调用；经 TurnRunner 的回合在 hub-turn（⑤d2）的采样重放 |
| `test_a_hotfix_gate_redelivery_keeps_the_version_and_the_original_baseline` | 2559 | PARTIAL | role_prompt 在记下的调用；热修补的重交归 ⑤g |
| `test_candidate_defects_go_to_the_final_review_which_cannot_pass_them` | 993 | PARTIAL | 终审的候选缺陷一节在记下的调用；经 Engine 的流转归 ⑤i |
| `test_review_history_survives_rework_and_seals_the_next_round` | 1152 | PARTIAL | 复审封板一节在记下的调用；经 Engine 的流转归 ⑤i |
| `test_unverified_external_facts_wait_for_the_owner` | 1745 | PARTIAL | 仓库外事实一节在记下的调用（其中有的当时的结果与重放对不上：多回合之后文件已变）；Engine 与 send --facts-checked 归 ⑤i、⑤j |
| `test_a_turn_killed_midway_restarts_in_a_new_session_and_is_requeued_only_once` | 1985 | PARTIAL | 续接说明在记下的调用；requeue 归 ⑤i |
| `test_requeue_leaves_unread_and_kernel_run_stages_alone` | 2029 | PARTIAL | 同上 |
| `test_the_gate_hotfix_turn_carries_the_executors_words` | 6622 | PARTIAL | 热修补的原话一节在记下的调用；经 Engine 的流转归 ⑤i |
| `test_a_timed_out_voided_turn_is_resumed_not_restarted` | 6669 | PARTIAL | “上一回合超时作废”一节在记下的调用（其中有的当时的结果与重放对不上）；经 Engine 的流转归 ⑤i |
| `test_a_voided_turn_that_did_not_time_out_gets_no_resume_hint` | 6695 | PARTIAL | “上一回合超时作废”一节不该出现，在记下的调用（当时的结果与重放对得上）；经 Engine 的流转归 ⑤i |
| `test_the_owners_rework_words_reach_the_reworked_stage_verbatim` | 6712 | PARTIAL | 站主的原话一节在记下的调用（其中有的当时的结果与重放对不上）；经 Engine 的流转归 ⑤i |

COVERED 11、PARTIAL 21。前几片留给 ⑤d 的 PARTIAL：⑤a 的 1807、7729 改成 COVERED（见上）；⑤c 的 5946、3692、3798、5856、7303 都经 TurnRunner，归 ⑤d2。
另有按种子生成的回合输入（第 ⑤a 片的随机主任务状态加回合输入用到的字段，乘全部岗位、有无输入目录、四种续接、报错与代办说明）与生成的过渡断言，不算进某个用例的覆盖。变异 ts/mutations/hub-d1.ts.json 37 个全部抓住（第一轮漏 2 个：模板只重读一次——“正被替换”那条靠时序碰运气，改成探针调用前写标记、写入的进程等标记再过 0.3 秒；说明行只认 r、R 前缀——后面的去引号顺手去掉了多留下的引号，加了以空白加引号开头的说明）；影子的变异加 S23，23 个全部抓住。

### ⑤d2 输入目录与 TurnRunner

做法：Python 探针 hub.audit_samples 跑 27 条直接用到 TurnRunner、stage_inputs 的用例，记下这两个的每一次顶层调用（TurnRunner.run 24 条用例共 59 次，stage_inputs 4 条用例各 1 次）。调用当时把用例的仓库整份拷进快照（不含 .git；符号链接与联接不拷，记下指向与种类）。TurnRunner 另记 launcher 写出的字节与交回的结果、回合号与新会话号、当时的秒数（回合里取的秒数钉成这一个），以及名册与交差文件哈希里用例此刻改过的键（与采样开始时比，对应 monkeypatch.setitem；autouse 夹具 pi_knows_every_flag 去掉协调人岗位的 routing，所以每次都带着协调人这一条）；stage_inputs 另记当时的 worktree 根目录与 INPUT_FILE_LIMIT（inputs_fixture 两样都换了）。结束后照 hub.turn、hub.inputs 收集产物当作“当时的结果”。契约 hub-turn 交给 Python、Node、Bun 先后在调用当时的那个目录里重放：快照还原回原位置、链接与联接照记下的重建，覆盖值两边设同一组；先核对 Python 重放与当时的结果（全部对上），再逐字节比三边。采样与重放都用假 pi（PI_DISPATCH_PI_CMD，设计稿第 3 节）：采样时 --help 的探测被 autouse 夹具换成全认，pi 不起；重放时两边去探假 pi 的 --help。与纯 pytest 的条件有三处不同，看记录时要知道：（1）采样当时就设了 PI_DISPATCH_PI_CMD，指向假 pi（契约断言记下的 39 条 pi 命令都以它开头）；（2）回合里的 time.time 钉在记下的秒数（不钉的话限流那条在全量跑时撞过一次跨秒）；（3）快照里符号链接与联接不拷，按记下的指向与种类在重放前重建。前几片留给 ⑤d2 的 PARTIAL 都改成了 COVERED（见上面 ⑤c、⑤d1 两节）；⑤c 的 7303 其实不经 TurnRunner，加进了 hub-audit 的采样清单。

| 用例 | 行 | 状态 | TS 契约 |
|---|---|---|---|
| `test_turn_runner_reports_when_the_rate_limit_lifts` | 2317 | COVERED | hub-turn：记下的 TurnRunner.run 三边在调用当时的目录里重放，先核对 Python 重放与当时的结果 |
| `test_session_ids_change_on_a_fresh_restart` | 3659 | COVERED | hub-turn：记下的 TurnRunner.run 三边在调用当时的目录里重放，先核对 Python 重放与当时的结果 |
| `test_claude_resumes_the_named_session_of_an_interrupted_turn` | 3717 | COVERED | hub-turn：记下的 TurnRunner.run 三边在调用当时的目录里重放，先核对 Python 重放与当时的结果 |
| `test_turn_with_api_error_says_so` | 3855 | COVERED | hub-turn：记下的 TurnRunner.run 三边在调用当时的目录里重放，先核对 Python 重放与当时的结果 |
| `test_claude_workers_return_to_the_workspace_after_each_command` | 5275 | COVERED | hub-turn：记下的 TurnRunner.run 三边在调用当时的目录里重放，先核对 Python 重放与当时的结果；两次调用都照记下的覆盖值：名册的 gate-sonnet 换成用例的 CLAUDE_GATE |
| `test_pi_workers_run_their_rostered_model_and_tools` | 5795 | COVERED | hub-turn：记下的 TurnRunner.run 三边在调用当时的目录里重放，先核对 Python 重放与当时的结果 |
| `test_a_throttled_pi_turn_is_held_with_a_growing_backoff` | 6013 | COVERED | hub-turn：记下的 TurnRunner.run 三边在调用当时的目录里重放，先核对 Python 重放与当时的结果（11 次；回合里取的秒数钉成记下的那一个） |
| `test_a_turn_whose_stream_hides_a_call_behind_u2028_is_voided` | 6928 | COVERED | hub-turn：记下的 TurnRunner.run 三边在调用当时的目录里重放，先核对 Python 重放与当时的结果；照记下的覆盖值：名册的 audit-sonnet 换成用例的 CLAUDE_AUDIT |
| `test_stage_inputs_copies_this_tasks_mailbox_contracts_and_evidence_read_only` | 7100 | COVERED | hub-turn：记下的 stage_inputs 三边在调用当时的目录里重放（worktree 根目录与 INPUT_FILE_LIMIT 照 inputs_fixture 换过的值），先核对 Python 重放与当时的结果 |
| `test_the_runner_keeps_the_listing_and_writes_long_prompts_into_the_inputs` | 7135 | COVERED | hub-turn：记下的 stage_inputs 三边在调用当时的目录里重放（worktree 根目录与 INPUT_FILE_LIMIT 照 inputs_fixture 换过的值），先核对 Python 重放与当时的结果；接着的 TurnRunner.run 同样重放 |
| `test_stage_inputs_does_not_follow_directory_links_or_junctions` | 7156 | COVERED | hub-turn：记下的 stage_inputs 三边在调用当时的目录里重放（worktree 根目录与 INPUT_FILE_LIMIT 照 inputs_fixture 换过的值），先核对 Python 重放与当时的结果；快照里的目录符号链接与联接各一个，重放前照记下的重建 |
| `test_stage_inputs_clears_this_tasks_leftover_directories` | 7187 | COVERED | hub-turn：记下的 stage_inputs 三边在调用当时的目录里重放（worktree 根目录与 INPUT_FILE_LIMIT 照 inputs_fixture 换过的值），先核对 Python 重放与当时的结果；比上一层剩下的目录 |
| `test_a_coordinator_turn_hands_in_through_deliver` | 7335 | COVERED | hub-turn：记下的 TurnRunner.run 三边在调用当时的目录里重放，先核对 Python 重放与当时的结果 |
| `test_a_gate_turn_hands_in_through_deliver` | 7366 | COVERED | hub-turn：记下的 TurnRunner.run 三边在调用当时的目录里重放，先核对 Python 重放与当时的结果 |
| `test_a_contract_turn_hands_in_through_deliver` | 7384 | COVERED | hub-turn：记下的 TurnRunner.run 三边在调用当时的目录里重放，先核对 Python 重放与当时的结果 |
| `test_a_changed_planner_schema_stops_the_claude_turn` | 7399 | COVERED | hub-turn：记下的 TurnRunner.run 三边在调用当时的目录里重放，先核对 Python 重放与当时的结果；照记下的覆盖值：DELIVERY_SHA256 的 planner.json（全零） |
| `test_the_planner_hands_in_through_claude_json_schema` | 7408 | COVERED | hub-turn：记下的 TurnRunner.run 三边在调用当时的目录里重放，先核对 Python 重放与当时的结果 |
| `test_no_deliver_or_a_bad_one_is_an_invalid_output` | 7449 | COVERED | hub-turn：记下的 TurnRunner.run 三边在调用当时的目录里重放，先核对 Python 重放与当时的结果 |
| `test_a_delivery_the_kernel_cannot_read_is_an_interface_error` | 7771 | COVERED | hub-turn：记下的 TurnRunner.run 三边在调用当时的目录里重放，先核对 Python 重放与当时的结果 |
| `test_a_changed_delivery_file_stops_the_turn` | 7829 | COVERED | hub-turn：记下的 TurnRunner.run 三边在调用当时的目录里重放，先核对 Python 重放与当时的结果；照记下的覆盖值：DELIVERY_SHA256 的 coordinator.json（全零） |

COVERED 20。另有手写的场景，不算进某个用例的覆盖：pi 的交差成功、复核不过、没交、读不到参数、非零退出、超时、限流的退避与清零、被拦；会话的续接、fresh、工作目录变了、半截换新、跳过已有的代、给定会话号；claude 的新会话、续接、生效档位、输入目录与长输入、依赖目录；名册与交差文件换过的场景（coordinator.json、planner.json、guard.ts 全零，名册的 gate-sonnet、audit-sonnet 换成与用例逐字段相同的 CLAUDE_GATE、CLAUDE_AUDIT）；只读输入目录；真的来源的形状核对；claude 的路径。变异：hub-d2.ts.json 34 个全部抓住（turn.ts 24 个、inputs.ts 10 个）；hub-shadow.ts.json 加 S24，24 个里 23 个第一轮抓住，S22 漏过一次，把会话文件的时刻错开后单独重跑抓住。

## ⑤e 合同与战前门禁

### ⑤e1a 纯文字的部分

做法：先在 test_kit_hub.py 全部用例上采样一次（参数化的与要别的夹具的 19 条采不了），挑出调到 tail、tail_file、normalize_identity、normalize_markup、strip_decisions、decisions_section、unparsed_check_ids、external_fact_problems、unverified_facts、pytest_outcomes 的 80 条；Python 探针 hub.audit_samples 记下它们对这十个函数的顶层调用（约 370 次；tail 164 次按“文字的 sha256、行数”去重，去掉 118–120 次，随用例文字里的时刻与临时路径变），契约 hub-contract 交给 Python、Node、Bun 逐字比，并要求每个函数都有 Python 重放与当时结果相同的样本（只比得上漂移了的不算）。当时的结果与 Python 重放对不上的 2 条（DRIFTED）都是 tail_file：用例读过的检查日志后来删了，重放时报 FileNotFoundError；tail_file 在另外 10 条用例里有比得上的样本。采样器这一片起照 pytest 截下用例的标准输出与标准错误（有的用例经 hub 打印中文，探针的 stdout 不是 UTF-8 时会崩在打印上；monkeypatch 的 undo 也在截下的范围里）。

| 用例 | 行 | 状态 | TS 契约 |
|---|---|---|---|
| `test_tail_file_reads_only_the_end` | 1139 | COVERED | hub-contract：记下的调用；「手写的对照」另有空文件、恰好 n 行、不以换行结尾、CRLF、单独的 CR、按字节截在多字节字符中间、文件不在与是目录 |
| `test_pytest_outcomes_reads_the_summary_not_the_captured_output` | 924 | PARTIAL | pytest_outcomes 在记下的调用与「手写的对照」（摘要行的各种写法、summary info 之前的 FAILED 不算、通用换行、Unicode 数字）；defect_matches 归 ⑤f |
| `test_bold_item_ids_in_the_contract_are_normalized` | 6303 | PARTIAL | normalize_markup 在记下的调用；accept_contract 归 ⑤e2 |
| `test_scope_notes_are_stripped_and_unparsed_check_ids_are_named` | 6406 | PARTIAL | normalize_markup、unparsed_check_ids 在记下的调用；contract_requirements 归 ⑤e1b |
| `test_decisions_are_attached_to_the_contract_and_shown_to_the_contract_writer` | 6486 | PARTIAL | strip_decisions、decisions_section 在记下的调用；accept_contract 归 ⑤e2，contract_requirements 归 ⑤e1b（⑤d1 记的那半照旧） |
| `test_plan_delivery_must_list_its_external_facts` | 1711 | PARTIAL | 参数化的用例采样器跑不了：它给 external_fact_problems 的五种输入（没有这个键、写成“无”、第 2 条缺 verified、缺 fact、条目是字符串）在「手写的对照」；经 Engine 的重交归 ⑤i |

COVERED 1、PARTIAL 5。其余 75 条只是经别的函数间接调到这十个（tail 在内核里有三十多处调用），覆盖记在它们的主体所在的片；这些调用在 hub-contract 里三边重放过。另有手写的对照（站主决定的附录与去掉、检查行编号、外部事实与没核实的事实、Identity 与粗体编号的边界与崩溃）与按种子生成的合同文字（掺全角标点、组合字符、希腊字母、Unicode 数字与空白、BMP 之外的字符），不算进某个用例的覆盖。变异 ts/mutations/hub-e1a.ts.json 31 条：第一轮 30 条抓住 29 条，漏掉的 E08（括号说明里允许嵌套）是因为用例里只有配平的嵌套括号，两种写法都匹配不上，补了一行括号没配平的 Scope 项之后单独重跑抓住。themistally-15 复核后：E12 原先靠崩溃抓住，换成语义上的“Scope 一节不在下一个标题处结束”；补 E31（单数的 warning 不改成复数，手写日志补一行 1 warning）；读文件改用 base 的 pyOSErrorOf、PyOSError 与 pyReadTextReplace，E03、E04 换锚点，E27 改打在 pyio.ts 的 pyReadTextReplace 上；这 5 条重跑都抓住。

### ⑤e1b 要读仓库、账本与信箱的部分

做法：照 ⑤e1a 先在全部用例上采样一次，挑出调到 contract_paths、scope_missing_prefix、contract_requirements、dod_coverage_problems、budget_problems、answers_question 的 44 条（其中 25 条只是顺带调到 contract_paths），契约 hub-contract-repo 三边重放记下的调用，每个函数都要有 Python 重放与当时结果相同的样本。DRIFTED 7 条：重放读的是用例跑完时的合同与 runs，用例在调用之后改写了同号合同或领取了新的 attempt；漂移的调用照样三边比。按问题文字对过账：只在漂移样本里出现过的几类（预算的第二条、未决标注）在「手写的对照」里都有。带 .git 的快照记录器做出来以后（⑤e2 第 6 节第 1 条），这 7 条改用调用当时的快照重放、从 DRIFTED 拿掉（⑤e2 的出口条件）。pi_dispatch 的 read_kernel_impl、argv_impl 不在 kit_hub 里、采样器包不到，只有手写的对照与按种子生成的命令行；四张转交名单的键逐张对照 Python。

| 用例 | 行 | 状态 | TS 契约 |
|---|---|---|---|
| `test_gate_pre_commit_bumps_a_dispatched_contract_and_keeps_the_hotfix_diff` | 373 | PARTIAL | contract_requirements 在记下的调用；accept_gate_pre 归 ⑤e2 |
| `test_gate_rework_resets_a_worktree_the_state_lost_track_of` | 426 | PARTIAL | 同上；workspace_status 与经 Engine 的返工归 ⑤e2、⑤i |
| `test_gate_pre_rejects_a_baseline_that_does_not_collect` | 474 | PARTIAL | contract_requirements 在记下的调用；accept_gate_pre 归 ⑤e2 |
| `test_gate_pre_baseline_must_fail_on_assertions` | 491 | PARTIAL | 同上；hollow_baseline_problems 归 ⑤e2 |
| `test_contract_with_pending_marks_is_rejected` | 521 | PARTIAL | 漂移（DRIFTED）：调用之后重交的 md 去掉了未决标注；未决标注的几种写法在「手写的对照」；⑤e2a 改用调用当时的快照后对上，见 ⑤e2a 一节 |
| `test_contract_budget_counts_attempts_of_earlier_versions` | 552 | PARTIAL | 漂移：几次调用之间改写同号合同的预算、领取新的 attempt；预算在「手写的对照」（runs 的四种形状、边界、各种取值）；⑤e2a 改用快照后对上 |
| `test_contract_delivery_is_refused_when_the_budget_leaves_one_attempt` | 574 | PARTIAL | 漂移：accept_contract 里随后把预算改大；accept_contract 归 ⑤e2 |
| `test_first_review_report_must_map_every_dod` | 662 | PARTIAL | dod_coverage_problems 在记下的调用与「手写的对照」（编号带正则的特殊字符）；经 Engine 的一审归 ⑤i |
| `test_contract_title_is_the_registered_task_title` | 901 | PARTIAL | contract_requirements 在记下的调用；revalidate_contract 归 ⑤e2 |
| `test_contract_requirements` | 1413 | PARTIAL | 漂移：同号合同一次次改写成不同的毛病，重放只读到最后一版；各种毛病在「手写的对照」；⑤e2a 改用快照后对上 |
| `test_kernel_writes_the_contract_version_and_base_it_assigns` | 1441 | PARTIAL | contract_requirements 在记下的调用；accept_contract 归 ⑤e2 |
| `test_contract_runs_the_earlier_gates_as_regression_checks` | 1472 | PARTIAL | 漂移：调用之后合同补上了回归检查；回归检查的缺与有在「手写的对照」；⑤e2a 改用快照后对上 |
| `test_unverified_external_facts_wait_for_the_owner` | 1745 | PARTIAL | answers_question 在记下的调用；经 Engine 的流转归 ⑤i |
| `test_a_hotfix_gate_redelivery_keeps_the_version_and_the_original_baseline` | 2559 | PARTIAL | contract_requirements 在记下的调用；热修补的重交归 ⑤g |
| `test_facts_checked_before_the_plan_is_delivered_says_why` | 5777 | PARTIAL | answers_question 在记下的调用；send 归 ⑤j |
| `test_scope_notes_are_stripped_and_unparsed_check_ids_are_named` | 6406 | PARTIAL | 漂移：调用之后重交的 md 改对了检查行编号；⑤e1a 那半照旧；⑤e2a 改用快照后对上 |
| `test_scope_paths_missing_the_directory_prefix_are_named` | 6430 | COVERED | hub-contract-repo：记下的调用；「手写的对照」另有带通配符、第一段在根下有、非 ASCII（git 整条加引号、对不上）、多于 6 条 |
| `test_decisions_are_attached_to_the_contract_and_shown_to_the_contract_writer` | 6486 | PARTIAL | 漂移：调用之后重交的 md 去掉了未决标注；accept_contract 归 ⑤e2 |
| `test_an_owner_reply_releases_the_gate_claim_and_long_letters_are_refused` | 6579 | PARTIAL | answers_question 在记下的调用；send 归 ⑤j |

COVERED 1、PARTIAL 18。另 25 条只是顺带调到 contract_paths，覆盖记在它们的主体所在的片。变异 ts/mutations/hub-e1b.ts.json 38 条全部抓住（contract.ts 的 ⑤e1b 部分 24 条、kernel-impl.ts 14 条：K14 是复核后补的“只有 TS 实现的命令先于 -h 判定”）；hub-c 加 C40（hub.audit 的 home 不还原），抓住。

选择文件与 argv_impl 在 Python 那边的用例在 tests/test_kernel_impl.py（不在 test_kit_hub.py 的 298 个场景里）。下面 8 条的 argv、impl 与 15 种坏写法原样抄进 hub-contract-repo 的手写对照，三边比（themistally-15 复核 ⑤e1b 时对出缺的 ui 带 -h、空文件、not json、schema_version 为 2、hub 为 None、config 为列表）。

| 用例（test_kernel_impl.py） | 行 | 状态 | TS 契约 |
|---|---|---|---|
| `test_a_missing_selector_means_all_python` | 99 | COVERED | hub-contract-repo：「test_kernel_impl.py」两条手写对照 |
| `test_a_valid_selector_is_read_as_is` | 103 | COVERED | hub-contract-repo：「test_kernel_impl.py」两条手写对照 |
| `test_a_broken_selector_refuses_to_run` | 127 | COVERED | hub-contract-repo：「test_kernel_impl.py」两条手写对照 |
| `test_an_unreadable_selector_refuses_to_run` | 135 | COVERED | hub-contract-repo：「test_kernel_impl.py」两条手写对照 |
| `test_argv_impl_uses_the_same_list` | 219 | COVERED | hub-contract-repo：「test_kernel_impl.py」两条手写对照 |
| `test_argv_impl_counts_ui_as_ts_whatever_the_selector` | 655 | COVERED | hub-contract-repo：「test_kernel_impl.py」两条手写对照 |
| `test_argv_impl_follows_the_config_switch` | 797 | COVERED | hub-contract-repo：「test_kernel_impl.py」两条手写对照 |
| `test_argv_impl_follows_the_dispatcher_switch` | 905 | COVERED | hub-contract-repo：「test_kernel_impl.py」两条手写对照 |

### ⑤e2a 内核调调度器，战前门禁里读工作区与基线记录的部分

做法：采样器加调用当时的快照（themistally-15 定的 ⑤e2 出口条件）。记下的函数在顶层被调时，把它读的仓库连 .git 整份拷一份；工作区是仓库外的 worktree（.git 是指针文件）时，连主仓库一起拷（worktree 的元数据在主仓库的 .git/worktrees 下）。三边重放前各自把快照原地放回。“顶层”只看这三个函数之间的嵌套，accept_gate_pre、accept_contract、run_exec 等里面的调用照样记下。在 test_kit_hub.py 全部用例上采样一次，24 条用例调到它们，共 100 次（workspace_status 44、contract_digest 36、hollow_baseline_problems 20），每一次的三边重放都与当时的结果相同。contract_digest 复核设计时以为只能手写（用例不直接调它），按这个口径有 36 次样本，照常进语料。run_pd 在用例里被 gate_setup 换成假调度器，采样记不到真的：真调度器上的 run_pd 由手写的对照去碰（经启动器，选择文件照常；照 test_kit_hub.py 里唯一直接调真 run_pd 的 test_the_ledger_records_which_implementation_answered 写），交回的文字与账本新增的一行三边逐字比；录制与重放注入归 ⑤e2b。

| 用例 | 行 | 状态 | TS 契约 |
|---|---|---|---|
| `test_gate_pre_commit_bumps_a_dispatched_contract_and_keeps_the_hotfix_diff` | 373 | PARTIAL | 调到的三个函数在调用当时的快照上对上；accept_gate_pre 归 ⑤e2b，Engine 归 ⑤i |
| `test_gate_rework_resets_a_worktree_the_state_lost_track_of` | 426 | PARTIAL | 调到的三个函数在调用当时的快照上对上；用例直接调的 workspace_status 也在其中；accept_gate_pre 归 ⑤e2b，经 Engine 的返工归 ⑤i |
| `test_gate_pre_rejects_a_baseline_that_does_not_collect` | 474 | PARTIAL | 调到的三个函数在调用当时的快照上对上；accept_gate_pre 归 ⑤e2b |
| `test_gate_pre_baseline_must_fail_on_assertions` | 491 | PARTIAL | 调到的三个函数在调用当时的快照上对上；用例直接调的 hollow_baseline_problems（十几种检查记录）全在其中；accept_gate_pre 归 ⑤e2b |
| `test_gate_post_judges_mutations_from_the_record` | 740 | PARTIAL | 调到的三个函数在调用当时的快照上对上；accept_gate_post 归 ⑤f |
| `test_gate_post_checks_the_anchors_before_mutating` | 795 | PARTIAL | 调到的三个函数在调用当时的快照上对上；accept_gate_post 归 ⑤f |
| `test_gate_post_reads_the_spec_file_and_names_entries_left_unchanged` | 837 | PARTIAL | 调到的三个函数在调用当时的快照上对上；accept_gate_post 归 ⑤f |
| `test_contract_title_is_the_registered_task_title` | 901 | PARTIAL | 调到的三个函数在调用当时的快照上对上；revalidate_contract 归 ⑤e2b |
| `test_gate_post_may_leave_the_candidate_red_with_evidence` | 938 | PARTIAL | 调到的三个函数在调用当时的快照上对上；accept_gate_post 归 ⑤f |
| `test_kernel_writes_the_contract_version_and_base_it_assigns` | 1441 | PARTIAL | 调到的三个函数在调用当时的快照上对上；accept_contract 归 ⑤e2b |
| `test_a_hotfix_gate_redelivery_keeps_the_version_and_the_original_baseline` | 2559 | PARTIAL | 调到的三个函数在调用当时的快照上对上；accept_gate_pre 归 ⑤e2b，热修补的重交归 ⑤g |
| `test_exec_rework_continues_from_the_reviewed_candidate` | 2770 | PARTIAL | 调到的三个函数在调用当时的快照上对上；run_exec 归 ⑤g |
| `test_rework_contract_lets_the_executor_modify_files_added_earlier` | 2842 | PARTIAL | 调到的三个函数在调用当时的快照上对上；run_exec 归 ⑤g |
| `test_retry_after_failed_checks_tells_the_executor_why` | 2926 | PARTIAL | 调到的三个函数在调用当时的快照上对上；run_exec 归 ⑤g |
| `test_post_gate_worktree_starts_from_the_attempt_base` | 3004 | PARTIAL | 调到的三个函数在调用当时的快照上对上；apply_candidate、attempt_base 归 ⑤f |
| `test_finished_tasks_remove_their_stage_worktrees` | 3276 | PARTIAL | 调到的三个函数在调用当时的快照上对上；retire_attempts 归 ⑤h，Engine 归 ⑤i |
| `test_worker_env_drops_the_decision_key_and_host_session_vars` | 3893 | COVERED | hub-contract-gate：kernel_env 的手写对照（决策 key 大写与小写两种写法都去掉，名字照 os.environ 原样比）；worker_env 在 ⑤c 的「手写的对照」 |
| `test_a_timed_out_attempt_is_continued_instead_of_restarted` | 5486 | PARTIAL | 调到的三个函数在调用当时的快照上对上；run_exec 归 ⑤g |
| `test_a_finished_attempt_whose_checks_failed_is_continued_instead_of_restarted` | 5534 | PARTIAL | 调到的三个函数在调用当时的快照上对上；run_exec 归 ⑤g |
| `test_an_unchanged_timed_out_attempt_keeps_the_same_rework_base` | 5585 | PARTIAL | 调到的三个函数在调用当时的快照上对上；run_exec 归 ⑤g |
| `test_a_gate_hotfix_moves_the_candidate_onto_the_new_baseline` | 5675 | PARTIAL | 调到的三个函数在调用当时的快照上对上；run_exec 归 ⑤g |
| `test_unsent_contracts_get_the_rostered_executor_line` | 5989 | PARTIAL | 调到的三个函数在调用当时的快照上对上；revalidate_contract、sync_executor_line 归 ⑤e2b |
| `test_a_cut_off_attempt_is_continued_instead_of_restarted` | 6101 | PARTIAL | 调到的三个函数在调用当时的快照上对上；run_exec 归 ⑤g |
| `test_an_unsent_contract_gets_the_rostered_executor_before_dispatch` | 6193 | PARTIAL | 调到的三个函数在调用当时的快照上对上；run_exec 归 ⑤g |
| `test_owner_raises_the_attempt_budget` | 6223 | PARTIAL | 调到的三个函数在调用当时的快照上对上；exec_marks 归 ⑤g，cmd_task_budget 归 ⑤j |
| `test_the_ledger_records_which_implementation_answered` | 6949 | COVERED | hub-contract-gate：真调度器上的 run_pd（--version 的退出码、输出里的 TOOL_VERSION、账本 dispatcher.called 的 impl 与 tool_version，三边逐字比） |

COVERED 2、PARTIAL 24：调到这三个函数的 24 条都是门禁、合同与执行流程里的一步，主体归 ⑤e2b、⑤f、⑤g、⑤h、⑤i；COVERED 的两条直接测 kernel_env 与真的 run_pd。hub-contract-gate 另有手写的对照：git status 的各种状态（暂存的改名照抄 Python 的毛病，迁移计划第 10.1 节）与仓库外的 worktree、合同两个文件在与不在、基线检查记录的每个分支、run_pd 的输出合并、账本、选择文件坏了记 invalid、超时，kernel_env 与 kernel_pytest_env 的名字，KERNEL_PYTEST。变异 ts/mutations/hub-e2a.ts.json 31 条：第一轮 29 条抓住 27 条；漏掉的 R03（mutate 起的命令本来就带 PYTHONDONTWRITEBYTECODE，只比名字看不出来）与 H10（超时那几条的退出码沿用了 1）补了用例（探针另交这个变量的值、契约先设成 0；退出码改成真实记录里的 null）之后单独重跑都抓住。复核后（themistally-15）kernel_env 改照 dict(os.environ)，R02（去 key 时分大小写）在 Windows 上成了等价变异，标 equivalent；补 R13（缺省的选择文件读 hub 仓库下的）与 R14（名字不照 os.environ 转大写）；H05 改由真的浮点退出码抓。这几条重跑：R01、R13、R14、H05 抓住，R02 记作预期内的等价。

⑤e1b 记成漂移的 7 条：读仓库的五个函数（scope_missing_prefix、contract_requirements、dod_coverage_problems、budget_problems、answers_question）改用调用当时的快照重放之后，hub-contract-repo 的 244 次调用全部与当时的结果相同，DRIFTED 拿掉（待办第 25 项）：

| 用例 | 行 | 状态 | TS 契约 |
|---|---|---|---|
| `test_contract_with_pending_marks_is_rejected` | 521 | COVERED | hub-contract-repo：调用当时的快照上的记下的调用（干净、两处未决标注、改成已确认，每一版都对上）；「手写的对照」另有未决标注的几种写法 |
| `test_contract_budget_counts_attempts_of_earlier_versions` | 552 | COVERED | hub-contract-repo：调用当时的快照上的 budget_problems（几次改写预算、领取新的 attempt，每一次都对上）；「手写的对照」另有 runs 的四种形状、边界、各种取值 |
| `test_contract_delivery_is_refused_when_the_budget_leaves_one_attempt` | 574 | PARTIAL | budget_problems 在调用当时的快照上对上；accept_contract 归 ⑤e2b |
| `test_contract_requirements` | 1413 | COVERED | hub-contract-repo：调用当时的快照上的记下的调用（同号合同一次次改写成不同的毛病，每一版都对上）；「手写的对照」另有各种毛病 |
| `test_contract_runs_the_earlier_gates_as_regression_checks` | 1472 | COVERED | contract_requirements 在调用当时的快照上对上（缺回归检查与补上之后）；regression_gates 与合同端的回合输入在 ⑤d1 的记下的调用 |
| `test_scope_notes_are_stripped_and_unparsed_check_ids_are_named` | 6406 | COVERED | ⑤e1a 的 normalize_markup、unparsed_check_ids 与这里的 contract_requirements（调用当时的快照上对上）合起来 |
| `test_decisions_are_attached_to_the_contract_and_shown_to_the_contract_writer` | 6486 | PARTIAL | contract_requirements 在调用当时的快照上对上；accept_contract 归 ⑤e2b |

这 7 条里 COVERED 5、PARTIAL 2。

### ⑤e2b 合同与战前门禁里改状态的部分

做法（设计稿第 6 节第 6 条、第 8 节，themistally-15 定的）：采样器的 flow_recorder 在 accept_contract、revalidate_contract、bump_contract_version、set_contract_base、accept_gate_pre、sync_executor_line 的最外层调用时记：调用当时的快照（带 .git，仓库外的门禁 worktree 一起）；钉住的时刻（kit_hub.utc_now、utc_compact 与 TS 的 withPinnedClock 钉在同一个微秒数上）；提交作者与日期（GIT_* 六个变量，只在这一次调用期间设）；用例当时换掉的 run_pd、contract_requirements、budget_problems、revalidate_contract 的每一次调用（参数、交回值、两棵树里的文件改动、调用之后的 ts）。三边先原地放回快照，再照记录注入（参数逐次核对，对不上、多调、少调都报错）重放，比交回值、调用之后的 ts、两棵树里新建/改动/删掉的文件（逐字节，.git 内部除外）、账本新增的部分、用命令读出的 git 状态（每棵树的 HEAD 与 status，全部引用）。这 23 条是在 test_kit_hub.py 全部能采样的用例上开着采样器跑一遍、按有没有最外层调用筛出来的；采不了的 19 条（参数化的与要别的夹具的，展开成 82 条）另用只计数的插件跑过，都没有走到这六个函数。23 条用例的 76 次调用，每一次三边都与当时的结果相同；只在比较这一步把交回值里 pytest 收集失败输出的用时换成占位（ts、文件、账本、git 状态照样逐字比）。

| 用例 | 行 | 状态 | TS 契约 |
|---|---|---|---|
| `test_dispatched_contract_is_bumped_not_edited` | 322 | COVERED | hub-contract-flow：bump 2 次（新版本、撞上已有的版本） |
| `test_gate_pre_commit_bumps_a_dispatched_contract_and_keeps_the_hotfix_diff` | 373 | PARTIAL | accept_gate_pre 3 次；Engine 归 ⑤i |
| `test_gate_rework_resets_a_worktree_the_state_lost_track_of` | 426 | PARTIAL | accept_gate_pre 2 次；经 Engine 的返工归 ⑤i |
| `test_gate_pre_rejects_a_baseline_that_does_not_collect` | 474 | COVERED | hub-contract-flow：accept_gate_pre 4 次（收集失败三次）；ensure_worktree 只用来搭门禁草稿 worktree，它本身归 ⑤i |
| `test_gate_pre_baseline_must_fail_on_assertions` | 491 | COVERED | hub-contract-flow：accept_gate_pre 1 次，加上 ⑤e2a 的 hollow_baseline_problems；ensure_worktree 同上 |
| `test_contract_delivery_is_refused_when_the_budget_leaves_one_attempt` | 574 | COVERED | hub-contract-flow：accept_contract 2 次，用例换上的 revalidate 照记录注入；guard 在 ⑤a |
| `test_contract_title_is_the_registered_task_title` | 901 | COVERED | hub-contract-flow：revalidate_contract 1 次（derive-json 带 --title） |
| `test_kernel_writes_the_contract_version_and_base_it_assigns` | 1441 | COVERED | hub-contract-flow：accept_contract 3 次；turn_prompt 在 ⑤d1 |
| `test_a_contract_that_fails_derive_json_is_redrafted_under_the_same_number` | 2519 | PARTIAL | accept_contract 2 次（同号重交）；Engine 的当场重交归 ⑤i |
| `test_a_hotfix_gate_redelivery_keeps_the_version_and_the_original_baseline` | 2559 | PARTIAL | accept_gate_pre 3 次；热修补的重交归 ⑤g |
| `test_exec_rework_continues_from_the_reviewed_candidate` | 2770 | PARTIAL | bump 2、set_contract_base 2、sync 5 次；run_exec 归 ⑤g |
| `test_rework_contract_lets_the_executor_modify_files_added_earlier` | 2842 | PARTIAL | bump 1、revalidate 2、sync 2 次；run_exec 归 ⑤g |
| `test_retry_after_failed_checks_tells_the_executor_why` | 2926 | PARTIAL | bump 2、revalidate 2、sync 5 次；run_exec 归 ⑤g |
| `test_a_timed_out_attempt_is_continued_instead_of_restarted` | 5486 | PARTIAL | bump、set_contract_base、sync 各 1 次；run_exec 归 ⑤g |
| `test_a_finished_attempt_whose_checks_failed_is_continued_instead_of_restarted` | 5534 | PARTIAL | bump、set_contract_base、sync 各 1 次；run_exec 归 ⑤g |
| `test_an_unchanged_timed_out_attempt_keeps_the_same_rework_base` | 5585 | PARTIAL | bump、set_contract_base、sync 各 1 次；run_exec 归 ⑤g |
| `test_a_gate_hotfix_moves_the_candidate_onto_the_new_baseline` | 5675 | PARTIAL | set_contract_base、sync 各 1 次；run_exec 归 ⑤g |
| `test_unsent_contracts_get_the_rostered_executor_line` | 5989 | COVERED | hub-contract-flow：revalidate 1 次、sync 2 次 |
| `test_a_cut_off_attempt_is_continued_instead_of_restarted` | 6101 | PARTIAL | bump、set_contract_base、sync 各 1 次；run_exec 归 ⑤g |
| `test_an_unsent_contract_gets_the_rostered_executor_before_dispatch` | 6193 | PARTIAL | sync 3 次、revalidate 2 次；run_exec 归 ⑤g |
| `test_owner_raises_the_attempt_budget` | 6223 | PARTIAL | bump 1 次、revalidate 2 次；exec_marks 归 ⑤g，cmd_task_budget 归 ⑤j |
| `test_bold_item_ids_in_the_contract_are_normalized` | 6303 | COVERED | hub-contract-flow：accept_contract 2 次 |
| `test_decisions_are_attached_to_the_contract_and_shown_to_the_contract_writer` | 6486 | COVERED | hub-contract-flow：accept_contract 3 次 |

COVERED 9、PARTIAL 14。hub-contract-flow 另有手写的对照：真调度器上的门禁基准测试（走通：收集、提交、挂引用、改 base_sha、derive-json、validate、baseline；收集失败）与 KERNEL_PYTEST 不在 worktree 里留缓存（PYTHONDONTWRITEBYTECODE 先设成 0）；accept_gate_pre、revalidate、accept_contract、bump、set_contract_base、sync 样本没走到的分支（假的 run_pd 照手写的记录注入）；注入核对的三种报错。调度器自己写的证据（baseline/NN/ 下）比路径清单，checks.json 里钉不住的字段打占位后逐字比，日志不比内容。变异 ts/mutations/hub-e2b.ts.json 49 条全部抓住：第一轮 47 条抓住 44 条，漏掉的 A01（缺“只有空白”的用例）、G09（用例里 baseline 的输出都不到 20 行）补了用例；G12 起初当成等价，themistally-15 复核时指出用例换上的假 revalidate 不碰合同哈希，补了 baseline 那次改合同 JSON 的场景；复核后另加 S02（base_sha 的行尾空白不跨行）与 W01（合同照 Node 的写法写，孤立代理项悄悄换成 U+FFFD）；改完整份重跑。

## ⑤f 战后门禁与变异

做法（⑤f 设计稿第 3、10 节，themistally-15 定的）：
- 改状态的五个函数（apply_candidate、ensure_worktree、seed_whitebox、accept_gate_post、run_mutations）照 ⑤e2b 的 flow_recorder 记、照调用当时重放。
- 注入名单：
  - 用例当时换掉的 run_pd、worktree_root 照记录注入。
  - 用例没换的两样也录下来注入：白盒测试那一次 pd.run_supervised（只在 accept_gate_post 里），建 worktree 的 tempfile.mkdtemp。
  - run_supervised 核对命令、目录、环境变量（两边各自与当场的 kernel_pytest_env() 整份比，值不进记录）、输出去向、时限、grace 与中断处理。
- mkdtemp 建出的目录是新的一棵树，重放前先删。
- 其余十个函数照 ⑤e2a 记：读文件的三个（attempt_base、unmutated_problems、gate_spec）带调用当时的快照。
- 从 ⑤f 起，探针对所有异常都交回 str(exc)，报错文字也逐字比；hub.call 与影子同样。

契约：
- hub-gatepost：样本是 41 条用例。
  - 改状态的五个函数 48 次：apply_candidate 1、ensure_worktree 16、seed_whitebox 4、accept_gate_post 25、run_mutations 2。
  - 注入 run_supervised 25、run_pd 24、mkdtemp 13、worktree_root 13，新建的树 13 次。
  - 其余 107 次：attempt_base 74、mutation_problems 14、defect_matches 8、mutant_timeout 4、unmutated_problems 3、expected_missed_everywhere 3、candidate_defects 1。
  - 三边重放与当时的结果逐字相同。
- hub-gatepost-scenes：16 组手写场景。
  - accept_gate_post 先挡下的几种与白盒测试的各种结果。
  - run_mutations 的时限、清单、锚点、记录、unmutated。
  - 纯函数的手写边界。
  - 按种子随机换类型的 1120 次调用。
  - 真 git 的 ensure_worktree、apply_candidate、seed_whitebox。
  - add_worktree 真失败三次（GIT_TRACE 数到 worktree add 正好 3 行）。
  - 真跑白盒 pytest、真跑 mutate（钉不住的照设计稿第 11.2 节打占位）。
- hub-gatepost-lock：别的进程拿着 .git-worktrees.lock 约 70 秒，三边都等满 60 秒、超时一次、再试时拿到锁建成。
- 另外几份契约：
  - pybase-config：sorted 的对照；Windows 错误文字的对照（WinError 2、183）；os.replace 的文字对照（WinError 32、5）。
  - attempt-commands、repo-commands：调度器三处 WinError 267 带文字比。

| 用例 | 行 | 状态 | TS 契约 |
|---|---|---|---|
| `test_gate_pre_commit_bumps_a_dispatched_contract_and_keeps_the_hotfix_diff` | 373 | PARTIAL | ensure_worktree 2 次（照调用当时重放）；accept_gate_pre 在 ⑤e2b，Engine 归 ⑤i |
| `test_gate_rework_resets_a_worktree_the_state_lost_track_of` | 426 | PARTIAL | ensure_worktree 2 次；经 Engine 的返工归 ⑤i |
| `test_gate_pre_rejects_a_baseline_that_does_not_collect` | 474 | COVERED | hub-gatepost：ensure_worktree 1 次；accept_gate_pre 在 ⑤e2b |
| `test_gate_pre_baseline_must_fail_on_assertions` | 491 | COVERED | hub-gatepost：ensure_worktree 1 次；accept_gate_pre 在 ⑤e2b |
| `test_mutation_verdict_reads_the_record_not_the_exit_code` | 681 | COVERED | hub-gatepost：mutation_problems 11 次；hub-gatepost-scenes 另有手写的记录与随机换类型 |
| `test_multi_command_mutation_verdict_splits_by_command_and_names_the_idle_one` | 707 | COVERED | hub-gatepost：mutation_problems 3 次；手写场景另有按命令拆开、一条都没抓住的命令 |
| `test_expect_missed_on_every_command_is_an_undeclared_equivalence` | 726 | COVERED | hub-gatepost：expected_missed_everywhere 3 次、run_mutations 1 次（hub 是 None）；ROLE_EXTRA_OUTPUT 的文字在 ⑤a |
| `test_gate_post_judges_mutations_from_the_record` | 740 | COVERED | hub-gatepost：accept_gate_post 5 次、ensure_worktree 1 次；turn_prompt 在 ⑤d1 |
| `test_gate_post_checks_the_anchors_before_mutating` | 795 | COVERED | hub-gatepost：accept_gate_post 2 次、ensure_worktree 1 次（用例当时的调度器照记录注入）；手写场景另有锚点核对没过的几种 |
| `test_gate_post_reads_the_spec_file_and_names_entries_left_unchanged` | 837 | COVERED | hub-gatepost：accept_gate_post 8 次、ensure_worktree 1 次；手写场景另有 gate_spec 的各个分支 |
| `test_pytest_outcomes_reads_the_summary_not_the_captured_output` | 924 | COVERED | hub-gatepost：defect_matches 8 次；pytest_outcomes 在 ⑤e1a |
| `test_gate_post_may_leave_the_candidate_red_with_evidence` | 938 | COVERED | hub-gatepost：accept_gate_post 10 次、ensure_worktree 1 次 |
| `test_mutant_timeout_follows_the_whitebox_time` | 1497 | COVERED | hub-gatepost：mutant_timeout 4 次；手写场景另有 11.8、12.0、20.0 秒与整份的时限 |
| `test_mutations_must_cover_the_changed_files` | 1531 | COVERED | hub-gatepost：run_mutations 1 次、unmutated_problems 3 次 |
| `test_a_hotfix_gate_redelivery_keeps_the_version_and_the_original_baseline` | 2559 | PARTIAL | ensure_worktree 3 次；热修补的重交归 ⑤g |
| `test_finalize_lands_the_oracle_commit_first_and_can_be_retried` | 2684 | PARTIAL | attempt_base 5 次；finalize 归 ⑤h |
| `test_exec_rework_continues_from_the_reviewed_candidate` | 2770 | PARTIAL | attempt_base 3 次；run_exec 归 ⑤g |
| `test_exec_rework_reports_when_the_rework_base_cannot_be_built` | 2826 | PARTIAL | attempt_base 3 次；run_exec 归 ⑤g |
| `test_post_gate_worktree_starts_from_the_attempt_base` | 3004 | COVERED | hub-gatepost：apply_candidate 1 次、attempt_base 1 次；手写场景另有打补丁、已打过、meta.json 坏了 |
| `test_finalize_lands_the_rework_chain_before_integrating` | 3024 | PARTIAL | attempt_base 6 次；finalize 归 ⑤h |
| `test_failed_integrate_takes_the_landed_commits_back_off_the_branch` | 3132 | PARTIAL | attempt_base 3 次；撤销落地归 ⑤h |
| `test_a_rework_commit_that_cannot_land_takes_the_oracle_back_off_too` | 3157 | PARTIAL | attempt_base 2 次；撤销落地归 ⑤h |
| `test_failed_integrate_names_the_meanwhile_commits_only_when_the_candidate_had_passed` | 3169 | PARTIAL | attempt_base 3 次；撤销落地归 ⑤h |
| `test_landing_is_not_undone_when_the_branch_moved_elsewhere_or_local_edits_block_it` | 3181 | PARTIAL | attempt_base 4 次；落地归 ⑤h |
| `test_retrying_finalize_does_not_pick_a_gate_the_owner_narrowed_again` | 3210 | PARTIAL | attempt_base 3 次；finalize 归 ⑤h |
| `test_owner_takeover_closes_the_task` | 3230 | PARTIAL | ensure_worktree 1 次；站主接手的命令归 ⑤j |
| `test_finished_tasks_remove_their_stage_worktrees` | 3276 | PARTIAL | ensure_worktree 2 次；retire_attempts 归 ⑤h，Engine 归 ⑤i |
| `test_the_review_record_names_the_model_of_the_final_audit_turn` | 3569 | PARTIAL | attempt_base 1 次；复审记录归 ⑤h |
| `test_a_kernel_revise_without_an_audit_says_so` | 3583 | PARTIAL | attempt_base 1 次；复审记录归 ⑤h |
| `test_landing_rehearsal_catches_a_gate_that_a_meanwhile_commit_breaks` | 4221 | PARTIAL | attempt_base 13 次；落地预演归 ⑤h |
| `test_landing_skips_an_empty_rework_commit` | 4274 | PARTIAL | attempt_base 4 次；落地归 ⑤h |
| `test_a_fresh_attempt_after_a_gate_hotfix_lands_without_the_old_rework_chain` | 4293 | PARTIAL | attempt_base 4 次；落地归 ⑤h |
| `test_landing_rehearsal_reports_commits_that_no_longer_apply` | 4324 | PARTIAL | attempt_base 4 次；落地预演归 ⑤h |
| `test_owner_commits_get_a_gate_sweep_and_rehearsals` | 4472 | PARTIAL | attempt_base 2 次；owner sweep 归 ⑤h |
| `test_new_attempt_gate_post_starts_from_the_previous_whitebox` | 5295 | COVERED | hub-gatepost：seed_whitebox 4 次；手写场景另有大小写不同的存档名、目标已在、已经放过、没有存档 |
| `test_a_timed_out_attempt_is_continued_instead_of_restarted` | 5486 | PARTIAL | attempt_base 2 次；run_exec 归 ⑤g |
| `test_a_finished_attempt_whose_checks_failed_is_continued_instead_of_restarted` | 5534 | PARTIAL | attempt_base 2 次；run_exec 归 ⑤g |
| `test_an_unchanged_timed_out_attempt_keeps_the_same_rework_base` | 5585 | PARTIAL | attempt_base 2 次；run_exec 归 ⑤g |
| `test_a_gate_hotfix_moves_the_candidate_onto_the_new_baseline` | 5675 | PARTIAL | attempt_base 4 次；run_exec 归 ⑤g |
| `test_a_cut_off_attempt_is_continued_instead_of_restarted` | 6101 | PARTIAL | attempt_base 2 次；run_exec 归 ⑤g |
| `test_a_gate_turn_hands_in_through_deliver` | 7366 | COVERED | hub-gatepost：candidate_defects 1 次；schema_errors 在 ⑤a，交差在 ⑤d2 |

COVERED 15、PARTIAL 26。PARTIAL 的 26 条，⑤f 的函数只是它们的一步，主体分别归 ⑤g、⑤h、⑤i、⑤j。

变异：ts/mutations/hub-f.ts.json 60 条，第一轮抓住 59 条；漏掉的 P57（没列的红用例只列前 10 条）补了 12 条都没列的场景之后，单独重跑抓住。ts/mutations/base-f.ts.json 5 条（pyset 的列表比较、replaceError、pyWinErrorMessage、relative_to 的文字）全部抓住。

其余场景随各片补（⑤g 到 ⑤j）。
