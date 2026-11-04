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
| `test_gate_pre_rejects_a_baseline_that_does_not_collect` | 474 | COVERED | hub-contract-flow：accept_gate_pre 4 次（收集失败三次）；ensure_worktree 只用来搭门禁草稿 worktree，它本身见 ⑤f 的表（hub-gatepost，COVERED） |
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

变异：ts/mutations/hub-f.ts.json 60 条，第一轮抓住 59 条；漏掉的 P57（没列的红用例只列前 10 条）补了 12 条都没列的场景之后，单独重跑抓住。ts/mutations/base-f.ts.json 5 条（pyset 的列表比较、replaceError、pyWinErrorMessage、relative_to 的文字）全部抓住。复核后（themistally-15 抽查 17 条，漏掉的是它自己设计的 X03–X05）补了三组手写场景：mutate 的 30 行输出（mutate_tail 与“没有跑完”都只附 25 行）、expect_missed 有两项以上又没列满、锚点对不上的条目名字不是字符串；并进 P61–P64，单独重跑都抓住。

## ⑤g 执行端代办与 JEV

⑤g 拆成两片（themistally-15 同意）：⑤g1 是只读与纯文字的部分，⑤g2 是改状态的部分（派遣、返工版本、重派合同、收尾、JEV）。

### ⑤g1 只读与纯文字的部分

做法（⑤g 设计稿第 3、10 节）：
- 读文件的十九个函数照 ⑤e2a 带调用当时的快照重放；快照与还原连文件、目录的修改时刻一起照原样（returned_blockers 拿 candidate.patch 的修改时刻跟终审记录比）。
- 只采 ⑤g1 的函数：run_exec 等 ⑤g2 的不包，经它们调到的 ⑤g1 函数也算顶层。

契约：
- hub-exec：44 条用例的 248 次调用三边重放，都与当时的结果相同。次数钉住：attempts_left 56、carry_source 51、empty_commit 44、gate_claims 16、
  failed_attempt 15、failed_checks_brief 13、rework_section 13、interrupted_attempt 6、jev_flag 6、add_modified_files 6、cut_off 5、failure_lines 5、
  unreported_gate_claims 5、returned_blockers 3、retry_section 2、report_leftovers 2；rework_source、latest_checks、carryable、checks_passed、
  unfinished_why、carry_back、rework_commits 没有顶层调用。
- hub-exec-scenes：14 组手写场景（attempt 目录的 23 种形状、接着改的各个来源、返工节与重派节的文字、add_modified_files 的 12 种写法、
  门禁有错的 31 种说法、jev_flag 的边界、修改时刻的同一秒与进位、真 git 的 empty_commit、按种子随机换类型的 660 次调用）。
- pybase-config：修改时刻换成秒的对照（40 个设在边界上的文件）。

| 用例 | 行 | 状态 | TS 契约 |
|---|---|---|---|
| `test_jev_report_flags_answers_by_the_battery_thresholds` | 1184 | COVERED | hub-exec：jev_flag 5 次 |
| `test_execution_jev_gets_the_objective_fingerprint` | 1196 | PARTIAL | jev_flag 1 次；派遣、收尾与 JEV（run_exec、finish_exec、run_jev）归 ⑤g2 |
| `test_requeue_leaves_unread_and_kernel_run_stages_alone` | 2029 | PARTIAL | interrupted_attempt 1 次；扣信、被打断的执行阶段与站主通知归 ⑤i |
| `test_a_stranded_exec_stage_is_reported_to_the_owner_once` | 2205 | PARTIAL | interrupted_attempt 1 次；扣信、被打断的执行阶段与站主通知归 ⑤i |
| `test_exec_verdict_reads_the_attempt_state_key` | 2641 | PARTIAL | attempts_left 4 次、gate_claims 1 次、failed_checks_brief 1 次；派遣、收尾与 JEV（run_exec、finish_exec、run_jev）归 ⑤g2 |
| `test_exec_recheck_revisits_the_last_attempt_without_rerunning` | 2661 | PARTIAL | attempts_left 1 次；finish_exec 经 kh.Engine 的 exec-recheck 调到，归 ⑤i（⑤g2 复核时改记） |
| `test_exec_rework_continues_from_the_reviewed_candidate` | 2770 | PARTIAL | attempts_left 5 次、carry_source 5 次、failed_attempt 3 次、empty_commit 2 次、rework_section 2 次；派遣、收尾与 JEV（run_exec、finish_exec、run_jev）归 ⑤g2 |
| `test_exec_rework_reports_when_the_rework_base_cannot_be_built` | 2826 | PARTIAL | attempts_left 2 次、carry_source 2 次；派遣、收尾与 JEV（run_exec、finish_exec、run_jev）归 ⑤g2 |
| `test_rework_contract_lets_the_executor_modify_files_added_earlier` | 2842 | PARTIAL | attempts_left 3 次、carry_source 3 次、failed_attempt 3 次、add_modified_files 2 次；派遣、收尾与 JEV（run_exec、finish_exec、run_jev）归 ⑤g2 |
| `test_add_modified_files_handles_both_list_forms` | 2902 | COVERED | hub-exec：add_modified_files 4 次 |
| `test_retry_after_failed_checks_tells_the_executor_why` | 2926 | PARTIAL | attempts_left 6 次、carry_source 6 次、failed_attempt 6 次、retry_section 2 次；派遣、收尾与 JEV（run_exec、finish_exec、run_jev）归 ⑤g2 |
| `test_exec_rework_stops_at_the_budget` | 2982 | PARTIAL | attempts_left 4 次；派遣、收尾与 JEV（run_exec、finish_exec、run_jev）归 ⑤g2 |
| `test_finalize_lands_the_rework_chain_before_integrating` | 3024 | PARTIAL | empty_commit 3 次；落地、结项与落地预演归 ⑤h |
| `test_failed_integrate_takes_the_landed_commits_back_off_the_branch` | 3132 | PARTIAL | empty_commit 2 次；落地、结项与落地预演归 ⑤h |
| `test_a_rework_commit_that_cannot_land_takes_the_oracle_back_off_too` | 3157 | PARTIAL | empty_commit 1 次；落地、结项与落地预演归 ⑤h |
| `test_failed_integrate_names_the_meanwhile_commits_only_when_the_candidate_had_passed` | 3169 | PARTIAL | empty_commit 2 次；落地、结项与落地预演归 ⑤h |
| `test_landing_is_not_undone_when_the_branch_moved_elsewhere_or_local_edits_block_it` | 3181 | PARTIAL | empty_commit 3 次；落地、结项与落地预演归 ⑤h |
| `test_retrying_finalize_does_not_pick_a_gate_the_owner_narrowed_again` | 3210 | PARTIAL | empty_commit 1 次；落地、结项与落地预演归 ⑤h |
| `test_landing_rehearsal_catches_a_gate_that_a_meanwhile_commit_breaks` | 4221 | PARTIAL | empty_commit 11 次；落地、结项与落地预演归 ⑤h |
| `test_landing_skips_an_empty_rework_commit` | 4274 | PARTIAL | empty_commit 9 次；落地、结项与落地预演归 ⑤h |
| `test_a_fresh_attempt_after_a_gate_hotfix_lands_without_the_old_rework_chain` | 4293 | PARTIAL | empty_commit 1 次；落地、结项与落地预演归 ⑤h |
| `test_landing_rehearsal_reports_commits_that_no_longer_apply` | 4324 | PARTIAL | empty_commit 3 次；落地、结项与落地预演归 ⑤h |
| `test_owner_commits_get_a_gate_sweep_and_rehearsals` | 4472 | PARTIAL | empty_commit 2 次；落地、结项与落地预演归 ⑤h |
| `test_exec_recheck_resumes_an_execution_the_hub_was_killed_in` | 5152 | PARTIAL | interrupted_attempt 4 次、attempts_left 1 次；finish_exec 经 kh.Engine 的 exec-recheck 调到，归 ⑤i（⑤g2 复核时改记） |
| `test_exec_waits_for_the_landing_lock_by_holding_its_letter` | 5360 | PARTIAL | attempts_left 1 次；扣信、被打断的执行阶段与站主通知归 ⑤i |
| `test_a_timed_out_attempt_is_continued_instead_of_restarted` | 5486 | PARTIAL | carry_source 7 次、attempts_left 1 次、empty_commit 1 次、failure_lines 1 次、rework_section 1 次；派遣、收尾与 JEV（run_exec、finish_exec、run_jev）归 ⑤g2 |
| `test_a_finished_attempt_whose_checks_failed_is_continued_instead_of_restarted` | 5534 | PARTIAL | rework_section 2 次、attempts_left 1 次、carry_source 1 次、empty_commit 1 次、failure_lines 1 次、report_leftovers 1 次；派遣、收尾与 JEV（run_exec、finish_exec、run_jev）归 ⑤g2 |
| `test_an_unchanged_timed_out_attempt_keeps_the_same_rework_base` | 5585 | PARTIAL | attempts_left 1 次、carry_source 1 次、empty_commit 1 次、failure_lines 1 次、rework_section 1 次；派遣、收尾与 JEV（run_exec、finish_exec、run_jev）归 ⑤g2 |
| `test_a_timed_out_attempt_whose_checks_passed_is_not_told_to_rerun_them` | 5626 | COVERED | hub-exec：rework_section 5 次、failure_lines 1 次 |
| `test_carry_after_an_upstream_redelivery_finds_the_latest_usable_attempt` | 5647 | COVERED | hub-exec：carry_source 6 次 |
| `test_a_gate_hotfix_moves_the_candidate_onto_the_new_baseline` | 5675 | PARTIAL | attempts_left 2 次、carry_source 2 次、returned_blockers 1 次、report_leftovers 1 次、rework_section 1 次；派遣、收尾与 JEV（run_exec、finish_exec、run_jev）归 ⑤g2 |
| `test_carried_candidate_gets_only_the_final_review_blockers_raised_after_it` | 5762 | COVERED | hub-exec：returned_blockers 2 次 |
| `test_a_cut_off_attempt_is_continued_instead_of_restarted` | 6101 | PARTIAL | carry_source 5 次、attempts_left 1 次、empty_commit 1 次、failure_lines 1 次、rework_section 1 次；派遣、收尾与 JEV（run_exec、finish_exec、run_jev）归 ⑤g2 |
| `test_an_abandoned_attempt_is_skipped_when_looking_for_a_candidate` | 6134 | COVERED | hub-exec：carry_source 6 次 |
| `test_exec_letter_counts_the_candidate_and_names_the_failed_checks` | 6160 | PARTIAL | attempts_left 4 次、gate_claims 2 次、unreported_gate_claims 2 次、failed_checks_brief 2 次、cut_off 2 次；派遣、收尾与 JEV（run_exec、finish_exec、run_jev）归 ⑤g2 |
| `test_an_unsent_contract_gets_the_rostered_executor_before_dispatch` | 6193 | PARTIAL | attempts_left 3 次、carry_source 3 次、failed_attempt 3 次；派遣、收尾与 JEV（run_exec、finish_exec、run_jev）归 ⑤g2 |
| `test_owner_raises_the_attempt_budget` | 6223 | PARTIAL | attempts_left 2 次；站主改预算的命令归 ⑤j |
| `test_an_unchanged_attempt_on_a_rework_base_still_carries_the_work` | 6324 | COVERED | hub-exec：carry_source 4 次 |
| `test_gate_claims_in_the_executor_report_are_found` | 6540 | COVERED | hub-exec：gate_claims 3 次 |
| `test_a_failed_attempt_claiming_gate_defects_waits_for_the_owner` | 6548 | PARTIAL | attempts_left 3 次、gate_claims 2 次、failed_checks_brief 2 次；派遣、收尾与 JEV（run_exec、finish_exec、run_jev）归 ⑤g2 |
| `test_gate_claims_only_in_the_thinking_are_held_when_there_is_no_report` | 6768 | PARTIAL | attempts_left 4 次、gate_claims 3 次、unreported_gate_claims 3 次、failed_checks_brief 3 次、cut_off 3 次；派遣、收尾与 JEV（run_exec、finish_exec、run_jev）归 ⑤g2 |
| `test_a_timed_out_attempt_that_changed_nothing_waits_for_the_owner` | 6808 | PARTIAL | attempts_left 3 次、gate_claims 3 次、failed_checks_brief 3 次；派遣、收尾与 JEV（run_exec、finish_exec、run_jev）归 ⑤g2 |
| `test_an_attempt_whose_candidate_was_not_collected_waits_for_the_owner` | 6834 | PARTIAL | attempts_left 2 次、gate_claims 2 次、failed_checks_brief 2 次；派遣、收尾与 JEV（run_exec、finish_exec、run_jev）归 ⑤g2 |
| `test_the_executor_letter_says_none_when_nothing_is_pending` | 7759 | PARTIAL | attempts_left 2 次；派遣、收尾与 JEV（run_exec、finish_exec、run_jev）归 ⑤g2 |

COVERED 8、PARTIAL 36。PARTIAL 的 36 条，⑤g1 的函数只是它们的一步，主体分别归 ⑤g2、⑤h、⑤i、⑤j。

变异：ts/mutations/hub-g1.ts.json 65 条：第一轮 61 条抓住 58 条，漏掉的 E12（返工链里没有 commit 的条目）、E30（Scope 标题前面的空白）、E59（四位数的 attempt）补了场景；写到一半复核后改的 pyCaught、pyIn 连同新加的 E60，7 条单独重跑都抓住；完整复核后 pyexc 补了 base 造得出的六个类名（BrokenPipeError、ConnectionError、ChildProcessError、BlockingIOError、TimeoutExpired、SubprocessError）与三边对照（继承关系逐对比 __mro__，认类逐个比 type(exc).__name__），并进 E61–E63（认不出 fsutil 的 UnicodeDecodeError、RecursionError 挂到 ValueError 下、ConnectionError 不算 OSError），单独重跑都抓住。themistally-15 另抽查的 X03（st_mtime 用 nsec / 1e9 算）、X04（微秒半数不取偶）判为等价：只出到秒，它在 Python 上跑的 40378 组时刻与 datetime.fromtimestamp 全同；X09（TS 探针还原时不设修改时刻）在 Windows 上 cpSync 照抄文件时刻、⑤g1 只比 candidate.patch，目录的时刻要到 final_audit_turn 才用上，届时补这条变异（final_audit_turn 实际在 ⑤g2 移植，X09 随 ⑤g2 补上，抓住）。

### ⑤g2 改状态的部分

做法（⑤g 设计稿第 12、13 节）：
- 有顶层调用的五个函数（run_exec、finish_exec、write_review、run_jev、ensure_rework_scope）照 ⑤e2b 的 flow_recorder 记、照调用当时重放。用例当时换掉的 run_pd、contract_requirements、rework_added_files、worktree_root、决策端的 Session（记它的 ask：设置的四样、账本路径、题库、state、context）与 load_locked_batteries，以及 rebase_candidate 建临时 worktree 的 mkdtemp，照记录注入，参数逐次核对。
- 落地锁被占的那一条（5360：用例在同一个进程里拿着锁，等锁时限改成 0.2 秒）不重放，契约钉住只跳这一条；手写场景里由另一个进程真的拿着锁。
- dispatch_attempt、start_rework、rebase_candidate、start_retry、rework_added_files、final_audit_turn、exec_window、scratch_worktree 只在里面被调到，由手写场景管。

契约：
- hub-runexec：31 条用例的 63 次顶层调用（run_exec 27、finish_exec 25、write_review 9、run_jev 1、ensure_rework_scope 1），跳过 1 次，62 次三边重放都与当时的结果相同，当时都是正常交回。注入：run_pd 86、contract_requirements 12、rework_added_files 10、mkdtemp 2、worktree_root 2、ask 1、load_locked_batteries 1；新建的 worktree 2 次。
- hub-runexec-scenes：15 组手写场景。
  - 派遣：走通的整条路（run 的退出码 0 与 124），attempt 路径的 8 种写法，run 时限的 24 种写法与回落，照样崩的 7 种。
  - finish_exec：门禁说法的截断、思考摘录、输出被截断时的自述、预算读不到、检查过了但有范围违规，以及 14 种怪类型。
  - final_audit_turn：目录的原始次序、同一秒、跳过的 9 种，照样崩的 2 种；有补丁时目录的时刻另设，since 只取补丁的。
  - write_review：已有记录时加 utc_compact，模型列表的几种写法，报告为空。
  - 真 git：rebase_candidate 5 种（含 2 MiB 的二进制改动），start_rework 8 种（is-ancestor 的 0、1、128），start_retry 3 种，ensure_rework_scope 与 rework_added_files 8 种。
  - run_exec：预算用完；另一个进程拿着落地锁，报 LandBusy；持有者已死时接管；派遣时执行标记被外面删了，收尾删不到照样吞掉。
  - run_jev 的真会话：传输层只认官方地址、改发本机的假端点，只给假 key，凭据库关掉；延时与时刻打占位。
- pybase-config：except OSError 认 Node 的文件错误。Python 真触发 7 种，类名与 Node 的错误经 pyExceptionName 的相同；Node 的参数错不算 OSError。

| 用例 | 行 | 状态 | TS 契约 |
|---|---|---|---|
| `test_execution_jev_gets_the_objective_fingerprint` | 1196 | COVERED | hub-runexec：run_jev 1 次 |
| `test_exec_verdict_reads_the_attempt_state_key` | 2641 | COVERED | hub-runexec：finish_exec 4 次 |
| `test_exec_recheck_revisits_the_last_attempt_without_rerunning` | 2661 | PARTIAL | finish_exec 1 次；finish_exec 经 kh.Engine 的 exec-recheck 调到；扣信、被打断的执行阶段与恢复归 ⑤i |
| `test_finalize_lands_the_oracle_commit_first_and_can_be_retried` | 2684 | PARTIAL | write_review 1 次；落地、结项与落地预演归 ⑤h |
| `test_exec_rework_continues_from_the_reviewed_candidate` | 2770 | COVERED | hub-runexec：run_exec 5 次 |
| `test_exec_rework_reports_when_the_rework_base_cannot_be_built` | 2826 | COVERED | hub-runexec：run_exec 2 次 |
| `test_rework_contract_lets_the_executor_modify_files_added_earlier` | 2842 | COVERED | hub-runexec：run_exec 3 次、ensure_rework_scope 1 次 |
| `test_retry_after_failed_checks_tells_the_executor_why` | 2926 | COVERED | hub-runexec：run_exec 6 次 |
| `test_exec_rework_stops_at_the_budget` | 2982 | COVERED | hub-runexec：run_exec 1 次、finish_exec 1 次 |
| `test_finalize_lands_the_rework_chain_before_integrating` | 3024 | PARTIAL | write_review 1 次；落地、结项与落地预演归 ⑤h |
| `test_failed_integrate_takes_the_landed_commits_back_off_the_branch` | 3132 | PARTIAL | write_review 1 次；落地、结项与落地预演归 ⑤h |
| `test_a_rework_commit_that_cannot_land_takes_the_oracle_back_off_too` | 3157 | PARTIAL | write_review 1 次；落地、结项与落地预演归 ⑤h |
| `test_failed_integrate_names_the_meanwhile_commits_only_when_the_candidate_had_passed` | 3169 | PARTIAL | write_review 1 次；落地、结项与落地预演归 ⑤h |
| `test_landing_is_not_undone_when_the_branch_moved_elsewhere_or_local_edits_block_it` | 3181 | PARTIAL | write_review 1 次；落地、结项与落地预演归 ⑤h |
| `test_retrying_finalize_does_not_pick_a_gate_the_owner_narrowed_again` | 3210 | PARTIAL | write_review 1 次；落地、结项与落地预演归 ⑤h |
| `test_the_review_record_names_the_model_of_the_final_audit_turn` | 3569 | COVERED | hub-runexec：write_review 1 次 |
| `test_a_kernel_revise_without_an_audit_says_so` | 3583 | COVERED | hub-runexec：write_review 1 次 |
| `test_exec_recheck_resumes_an_execution_the_hub_was_killed_in` | 5152 | PARTIAL | finish_exec 1 次；finish_exec 经 kh.Engine 的 exec-recheck 调到；扣信、被打断的执行阶段与恢复归 ⑤i |
| `test_exec_waits_for_the_landing_lock_by_holding_its_letter` | 5360 | PARTIAL | run_exec 1 次；落地锁被占的那一条不重放（契约钉住只跳它），由手写场景里另一个进程真的拿着锁；扣信、被打断的执行阶段与恢复归 ⑤i |
| `test_a_timed_out_attempt_is_continued_instead_of_restarted` | 5486 | COVERED | hub-runexec：run_exec 1 次 |
| `test_a_finished_attempt_whose_checks_failed_is_continued_instead_of_restarted` | 5534 | COVERED | hub-runexec：run_exec 1 次 |
| `test_an_unchanged_timed_out_attempt_keeps_the_same_rework_base` | 5585 | COVERED | hub-runexec：run_exec 1 次 |
| `test_a_gate_hotfix_moves_the_candidate_onto_the_new_baseline` | 5675 | COVERED | hub-runexec：run_exec 2 次 |
| `test_a_cut_off_attempt_is_continued_instead_of_restarted` | 6101 | COVERED | hub-runexec：run_exec 1 次 |
| `test_exec_letter_counts_the_candidate_and_names_the_failed_checks` | 6160 | COVERED | hub-runexec：finish_exec 4 次 |
| `test_an_unsent_contract_gets_the_rostered_executor_before_dispatch` | 6193 | COVERED | hub-runexec：run_exec 3 次 |
| `test_a_failed_attempt_claiming_gate_defects_waits_for_the_owner` | 6548 | COVERED | hub-runexec：finish_exec 3 次 |
| `test_gate_claims_only_in_the_thinking_are_held_when_there_is_no_report` | 6768 | COVERED | hub-runexec：finish_exec 4 次 |
| `test_a_timed_out_attempt_that_changed_nothing_waits_for_the_owner` | 6808 | COVERED | hub-runexec：finish_exec 3 次 |
| `test_an_attempt_whose_candidate_was_not_collected_waits_for_the_owner` | 6834 | COVERED | hub-runexec：finish_exec 2 次 |
| `test_the_executor_letter_says_none_when_nothing_is_pending` | 7778 | COVERED | hub-runexec：finish_exec 2 次 |

COVERED 21、PARTIAL 10。⑤g1 表里归 ⑤g2 的 21 条：19 条转 COVERED（上表）；2661、5152 的 finish_exec 经 kh.Engine 的 exec-recheck 调到，仍是 PARTIAL，改记归 ⑤i（⑤g1 表一并改了）。另加 3569、3583（只调 write_review）。PARTIAL 的 10 条：结项里调到 write_review 的 7 条归 ⑤h；2661、5152、5360 归 ⑤i。

变异：ts/mutations/hub-g2.ts.json 58 条（runexec.ts 的 R01–R56 少 R53，加探针的 X09 与抽查补的 X10、X11），跑手写场景与采样契约：R 的 55 条抓住 53 条。R18（git diff 的输出按字节判空白改成解码之后 trim）事先判为等价：git diff 的输出要么为空、要么以 diff --git 开头。R51（交给 Session 的题库不带阈值）第一轮意外漏掉，查明 Session.ask 两边都只读题库的 id、version、sha256、questions，标留意用的阈值是 run_jev 自己从题库字典取的，判为等价。X09（TS 探针还原时不设修改时刻；themistally-15 在 ⑤g1 抽查，当时目录的时刻还没人用，留到 final_audit_turn 落地再补）单独跑抓住（挂的是 final_audit_turn 没有补丁、看目录时刻的那组场景）。ts/mutations/base-g2.ts.json 4 条（pyexc 认 Node 的文件错误：EISDIR 另归、不看 syscall、ENOTDIR 归 OSError、一律认不出）全部抓住。themistally-15 在自己的副本上抽查 11 条（R15、R16、R17、R44、R48、X09 与它另加的 Y02、Y08、Y10、Y17、Y18），10 条抓住。Y02（exec_window 收尾删执行标记出错不再吞掉）第一轮漏掉：Python 内核自己不删这个标记，只有站主手动删了、别的进程占着文件才走得到；补了场景（派遣时标记被外面删了），并进 X10，它重跑抓住。Y08（check_ok 不看范围违规）漏掉：Python 用例的 attempt_dir 从没给 finish_exec 带违规的 scope.json，采样只见过空的违规；补了场景（NEEDS_REVIEW、检查过了、有一条违规，check_ok 是 false），并进 X11，单独跑抓住。中途两次被系统按内存不足停掉（themistally-15 的抽查一次、单跑 X10 一次，其间有外部经 SSH 起的 Java 构建），用户同意后在内存回升时重跑。

## ⑤h 结项、落地与后台回归

⑤h 拆成两片（themistally-15 同意）：⑤h1 是结项与落地、结项后的收尾，⑤h2 是后台回归与落地预演。

### ⑤h1 结项与落地、结项后的收尾

做法（⑤h 设计稿，themistally-15 复核）：
- 改状态的十个函数（finalize、landing_blockers、retire_attempts、tidy_finished、remove_workspaces、commit_records、land_oracle、land_rework_chain、undo_landing、record_pass）照 ⑤e2b 的 flow_recorder 记、照调用当时重放。用例当时换掉的 run_pd 与调度器的 _running_attempts 照记录注入；landing_blockers 里的 pd.pid_alive 一律照记录注入（执行标记记的是采样进程的 pid，重放时那个进程已经不在）。
- landed_meanwhile、landing_chain、on_branch 放回调用当时的快照之后三边逐字比（on_branch 在落地预演的临时 worktree 里看时，快照连 where 一起存）；landing_records 是纯函数。
- 语料：挂插件把 tests/test_kit_hub.py 全部跑一遍，看谁调到了这十四个函数，得 22 条；test_status_shows_the_parallel_runners 要 pytest 的 capsys，采样器不搭，不收。
- 6 次调用重放不出来，钉在契约的 UNREPLAYABLE 表里，每一条写明原因与覆盖它的手写场景，契约核对每一条恰好对上一次调用：3276 的 tidy_finished 4 次与 retire_attempts 第 2 次（仓库外的 worktree 在调用之间被用例删改，快照不带）；3181 的第 1 次 finalize（假的 integrate 在调用期间 reset --hard 挪了分支，注入只重放文件）。
- 采样器跑用例期间把文件描述符 1、2 接到空设备（exclusive 起的子进程直接写 1，会混进探针交回结果的通道）；注入的异常里，调度器的 DispatchError 与 OSError 一族照真的类抛（采样当时就是真的类）。

契约：
- hub-land：21 条用例。流程函数的顶层调用 55 次（finalize 20、landing_blockers 19、retire_attempts 4、tidy_finished 5、commit_records 2、land_oracle 2、land_rework_chain 3；remove_workspaces、undo_landing、record_pass 只在里面被调到），跳过 6 次，49 次三边重放都与当时的结果相同；注入 run_pd 25、_running_attempts 19、pid_alive 10。快照与纯函数 45 次（landed_meanwhile 7、landing_chain 11、on_branch 25、landing_records 2）三边相同。
- hub-land-scenes：15 组手写场景。
  - landing_blockers：标记的各种写法（没有 pid、pid 在、不在、字符串 0（pid_alive 交回 None）、浮点、True；有 label、只有 task、两样都没有；sweep 标记在 sweeps 为真、假、别的真值与假值时；坏 JSON、不是 UTF-8、目录、大写扩展名、不是 .json；NTFS 列目录与 Python 排序次序不同的两个名字），调度器记着在跑的 attempt（自己合同的滤掉）；注入的 _running_attempts（正反斜杠、前缀相同的别的合同、DispatchError 与 OSError 当成空、别的照样崩）与 pid_alive 的真、假、None；照样崩的 4 种。
  - finalize：verdict 被拒；基准测试挑不上，不再落返工链；integrate 没过，列出期间先落地的提交、撤回并恢复记录；过了之后提交记录，分支前进时记回归待跑、没前进时不记。
  - undo_landing 直接调：末端没动、已经不是祖先、reset --keep 被本地改动挡住、撤回并恢复记录；记录是列表时撤回之后照样崩。场景的仓库设 core.checkStat=minimal 与 core.trustctime=false（放回快照会换掉 ctime 与 inode）。
  - commit_records：Windows 上不分大小写、后缀分大小写、前缀相同的别的合同族不算，复审记录目录一起提交；没东西可提交、什么都没有；add 报错；照样崩的 2 种。
  - retire_attempts：没开跑且干净（cleanup --force）、没开跑但不干净、PREPARED 已开跑与 RUNNING 不动、mark 失败、有结论的只清 worktree 且 cleanup 失败、没有 worktree、目录名大写；照样崩的 4 种。
  - remove_workspaces 与 tidy_finished：真删一个 worktree、路径已不在、空路径与已删过的跳过、不是 worktree 的目录删不掉；照样崩的 3 种。
  - land_oracle 5 种；land_rework_chain 两条链（已落地的跳过、already、empty、ff、cherry-pick、挑不上停下；按 attempt 的基线筛、提交不存在照挑并报错）；on_branch、landing_chain、landed_meanwhile 直接调 6 种。

| 用例 | 行 | 状态 | TS 契约 |
|---|---|---|---|
| `test_finalize_lands_the_oracle_commit_first_and_can_be_retried` | 2684 | COVERED | hub-land：finalize 5 次 |
| `test_finalize_lands_the_rework_chain_before_integrating` | 3024 | COVERED | hub-land：finalize 5 次 |
| `test_failed_integrate_takes_the_landed_commits_back_off_the_branch` | 3132 | COVERED | hub-land：finalize 2 次 |
| `test_a_rework_commit_that_cannot_land_takes_the_oracle_back_off_too` | 3157 | COVERED | hub-land：finalize 1 次 |
| `test_failed_integrate_names_the_meanwhile_commits_only_when_the_candidate_had_passed` | 3169 | COVERED | hub-land：finalize 2 次、landed_meanwhile 1 次 |
| `test_landing_is_not_undone_when_the_branch_moved_elsewhere_or_local_edits_block_it` | 3181 | COVERED | hub-land：finalize 3 次（第 1 次不重放：假的 integrate 在调用期间挪了分支，由手写场景直接调 undo_landing 的“已经不是祖先”覆盖）、landing_records 1 次 |
| `test_retrying_finalize_does_not_pick_a_gate_the_owner_narrowed_again` | 3210 | COVERED | hub-land：finalize 2 次、landing_records 1 次、on_branch 3 次 |
| `test_owner_takeover_closes_the_task` | 3230 | PARTIAL | tidy_finished 1 次；task close 的命令归 ⑤j |
| `test_finished_tasks_remove_their_stage_worktrees` | 3276 | PARTIAL | tidy_finished 4 次、retire_attempts 4 次，其中 5 次不重放（仓库外的 worktree 在调用之间被删改），由手写场景覆盖；Engine 归 ⑤i |
| `test_landing_waits_for_other_tasks_executors` | 4001 | PARTIAL | landing_blockers 3 次；land 归 ⑤i |
| `test_exec_window_marks_the_run_and_waits_for_a_landing` | 4034 | COVERED | hub-land：landing_blockers 1 次（exec_window 在 ⑤g2） |
| `test_records_commit_takes_only_the_tasks_plans_and_reviews` | 4131 | COVERED | hub-land：commit_records 2 次 |
| `test_landing_rehearsal_catches_a_gate_that_a_meanwhile_commit_breaks` | 4221 | PARTIAL | landing_chain 5 次、on_branch 11 次、landed_meanwhile 3 次；rehearse_landing 归 ⑤h2 |
| `test_landing_skips_an_empty_rework_commit` | 4274 | PARTIAL | land_oracle 1 次、land_rework_chain 2 次、landing_chain 1 次、on_branch 4 次；rehearse_landing 归 ⑤h2 |
| `test_a_fresh_attempt_after_a_gate_hotfix_lands_without_the_old_rework_chain` | 4293 | PARTIAL | land_oracle 1 次、land_rework_chain 1 次、landing_chain 2 次、on_branch 2 次；rehearse_landing 归 ⑤h2 |
| `test_landing_rehearsal_reports_commits_that_no_longer_apply` | 4324 | PARTIAL | landing_chain 2 次、on_branch 3 次、landed_meanwhile 2 次；rehearse_landing 归 ⑤h2 |
| `test_exclusive_runs_the_command_once_executors_are_done` | 4427 | PARTIAL | landing_blockers 2 次（sweeps=False）；cmd_exclusive 归 ⑤j |
| `test_exclusive_marks_an_owner_sweep_only_when_head_moves` | 4448 | PARTIAL | landing_blockers 3 次（sweeps=False）；mark_owner_moved 归 ⑤h2，cmd_exclusive 归 ⑤j |
| `test_owner_commits_get_a_gate_sweep_and_rehearsals` | 4472 | PARTIAL | landing_chain 1 次、on_branch 2 次、landed_meanwhile 1 次；owner sweep 归 ⑤h2 |
| `test_landing_waits_for_a_background_gate_sweep` | 4519 | PARTIAL | landing_blockers 6 次（sweeps 为假 2 次）；sweep_window 归 ⑤h2，cmd_exclusive 归 ⑤j |
| `test_background_sweeps_hold_off_other_landings_while_they_run` | 4545 | PARTIAL | landing_blockers 4 次；owner sweep 归 ⑤h2，Engine 归 ⑤i |

COVERED 9、PARTIAL 12。⑤g2 表里归 ⑤h 的 7 条结项用例（2684–3210）在这里转 COVERED；落地预演、owner sweep 与 sweep_window 的 8 条（4221、4274、4293、4324、4448、4472、4519、4545 里的 ⑤h2 部分）归 ⑤h2；3276、4001、4545 的 Engine 与 land 归 ⑤i；3230、4427、4448、4519 的命令归 ⑤j。

变异：ts/mutations/hub-h1.ts.json 78 条（land.ts 的 L01–L89，编号有空），抓住 77 条，L46 等价。先只跑手写场景，68 条抓住 65 条；漏掉的 3 条都是场景没构造到，补了场景之后用清单里的完整命令（手写场景加采样契约）重跑：L22（基准测试挑不上照样落返工链；原来那一轮返工被 attempt 的基线筛掉，挑不挑都一样，改成 meta.json 的 base_sha 指向它）与 L74（mark 失败照样清 worktree；原来那个 attempt 没有 worktree）抓住；L46（commit 不带 --only）判为等价：git commit 在命令行给了路径时缺省就是 --only，临时仓库里实测站主暂存的别的文件照旧留在暂存区；等价靠的是前面没有路径就早退，只有空路径时 --only 才起作用（git 报错，而不是把站主暂存的东西提交掉），themistally-15 复核时指出，补了删掉早退的 L48 与没有记录、站主暂存了文件的场景，L48 抓住。themistally-15 点名的短路条件（L01、L02、L04–L12、L27、L28、L50、L55、L56、L70–L73、L75、L76）都抓住；L16（标记不排序）抓住：NTFS 列目录照 $UpCase 比，Python 按小写比，_ 与字母的先后不同。themistally-15 在自己导出的副本上抽查 13 条（清单里的 L05、L16、L22、L48、L57、L74、L75、L76 与它另加的 X01–X05），10 条抓住；X01（阶段 worktree 不按 kind 排序）、X02（verdict 被拒的输出少取一行）、X05（integrated 少记一行）漏掉：场景里 workspaces 的键本来就按字母序插入，注入的输出都只有一行。补了场景（键倒着插、两个能删成功；注入的输出加长到各处 tail 的行数都起作用），连同同一次改动管到的 integrate 问题与落地之后的 detail、retire 的两处、cherry-pick 冲突输出的两处 tail，并进清单为 L81–L89，单独跑 9 条全部抓住。

### ⑤h2 后台回归与落地预演

做法（⑤h 设计稿，themistally-04 复核）：
- 改状态的六个函数（regression_sweep、rehearse_landing、rehearsal_letter、mark_owner_moved、owner_sweep、ts_install_if_stale）照 ⑤e2b 的 flow_recorder 记、照调用当时重放。
  - sweep_gates 与建临时 worktree 的 mkdtemp，在 regression_sweep、rehearse_landing、owner_sweep 里一律照记录注入：门禁基准在重放里不真跑，真跑放在手写场景里。
  - 用例当时换掉的 worktree_root、rehearse_landing、ts_install_if_stale，与调度器的 find_bun、read_kernel_impl，也照记录注入。
- ts_install_if_stale 的 runner：
  - 用例给了 runner 时，采样器把它换成录制包装，按内层的 run_supervised（内层名 ts_runner）注入，样本里 runner 记成 None；
  - stdout、stderr 是文件对象时，记成 <temporary> 与 same（Windows 上 TemporaryFile 的 name 是路径字符串，所以按有没有 write 判断）；
  - 环境与各自的 kernel_env() 比；
  - 输出记原始字节，读完放回原来的文件位置，重放时原样写进 stdout。
- read_owner_sweep 放回调用当时的快照之后，三边逐字比。
- 信的编号（themistally-04 定的）：
  - 钉住时刻时，new_msg_id 的后六位按调用次序从 000000 编起（%06x）。原来是随机后缀，写信的 6 次重放对不上。
  - Python 的采样与重放都换掉，finally 里还原；TS 在 withPinnedClock 里存下、还原计数。
  - 生产代码不钉时刻，withPinnedClock 只有 hub_probe 用，行为不变。
- 时限分开（themistally-04 复核时指出）：
  - EXEC_LAND_WAIT_SECONDS（60，exec_window）与 LAND_WAIT_SECONDS（3600，sweep_window 与 ts 重装）各有各的 deps 字段：landWaitSeconds、landLockWaitSeconds；
  - 请求键也分开：land_wait 与 land_lock_wait；SWEEP_WAIT_SECONDS、SWEEP_SECONDS 另有 sweep_wait、sweep_seconds；
  - 两边探针对称，finally 里还原。
- 采样器的修补：
  - 用例换掉 subprocess.Popen 时（supervisor 用例的 FakeProc），_flow_git 改用探针导入时存下的真 Popen；
  - hub 仓库不在时（用例故意给的另一处路径），不存快照。
- 语料：⑤h1 挂插件跑全部用例时，调到这几个函数的 24 条。

契约：
- hub-sweep：24 条用例。
  - 流程函数的顶层调用 39 次（regression_sweep 2、rehearse_landing 15、rehearsal_letter 2、mark_owner_moved 7、owner_sweep 6、ts_install_if_stale 7），没有跳过，三边重放都与当时的结果相同。
  - 注入：sweep_gates 14、mkdtemp 16、worktree_root 15、read_kernel_impl 6、find_bun 4、ts_runner 3、rehearse_landing 1、ts_install_if_stale 1。
  - read_owner_sweep 43 次，放回快照之后三边相同。
- hub-sweep-scenes：15 组手写场景。
  - sweep_gates 与 gate_baselines：
    - 真跑两份小门禁，一过一不过：文件名带大写的 B，码点排序在 a 前；不带 _baseline 的与 .txt 不选；仓库的 pytest.ini 写了 addopts = -rN，命令行的 -rfE 照样盖过它；
    - 没有门禁基准；
    - 只测 TS 的时限：按时交回，孙进程跟着整棵树结束，临时目录删掉。
  - .sweep 与 .land：
    - TS 挂着窗口时，Python 的 landing_blockers 认它的标记；Python 挂着时，TS 的也认；sweeps 为假时两边都不算；
    - TS 等 .sweep 超时，HubError 原样抛出；
    - 另一个进程拿着 .land 时，owner_sweep 与 ts 重装都原样抛出，.sweep 放掉；
    - 只测 TS 的那条核对：等 .land 用的是 landLockWaitSeconds。
  - regression_sweep：没有门禁基准；没过（输出长过 15 行）；过了。
  - owner_sweep：
    - 没有待跑；
    - 没过：期间的提交 12 个，主题长的截 600 字，主题短的只列 10 个；跑的期间站主又动了 HEAD，pending 留着；
    - 过了：执行标记被外面删了，收尾吞掉；先查一次 ts/ 的依赖；
    - 收了尾的任务，条件齐全也不预演。
  - ts_install_if_stale：
    - 不装的三种；
    - 要装的七种：戳记坏 JSON、是数组、哈希不对；装好了（输出长过 10 行，夹着非 UTF-8 的字节）；装完戳记对不上；超时，退出码 None 与 0 各一种，摘要长过 1500 字。
  - mark_owner_moved、read_owner_sweep、rehearsal_letter 的边界与截断。
  - rehearse_landing：
    - 门禁没过、基准测试挑不上、补丁打不上、ts 没有 oracle 照样崩；
    - 四道早退：末端就是 base_head、预演过、check 没过、oracle 是空提交。

| 用例 | 行 | 状态 | TS 契约 |
|---|---|---|---|
| `test_supervisor_runs_one_runner_per_task_up_to_the_limit` | 4050 | PARTIAL | read_owner_sweep 5 次；supervisor 归 ⑤j |
| `test_regression_sweep_runs_every_gate_baseline_on_the_new_tip` | 4152 | COVERED | hub-sweep：regression_sweep 2 次（注入 sweep_gates 2 次；真跑门禁在 hub-sweep-scenes） |
| `test_landing_rehearsal_catches_a_gate_that_a_meanwhile_commit_breaks` | 4221 | COVERED | hub-sweep：rehearse_landing 8 次（注入 sweep_gates 5 次；⑤h1 的部分在 hub-land） |
| `test_landing_skips_an_empty_rework_commit` | 4274 | COVERED | hub-sweep：rehearse_landing 1 次（⑤h1 的部分在 hub-land） |
| `test_a_fresh_attempt_after_a_gate_hotfix_lands_without_the_old_rework_chain` | 4293 | COVERED | hub-sweep：rehearse_landing 1 次（⑤h1 的部分在 hub-land） |
| `test_landing_rehearsal_reports_commits_that_no_longer_apply` | 4324 | COVERED | hub-sweep：rehearse_landing 5 次（⑤h1 的部分在 hub-land） |
| `test_exec_delivery_carries_the_rehearsal_and_warns_the_owner` | 4340 | PARTIAL | rehearsal_letter 1 次；Engine 的执行端交付归 ⑤i |
| `test_after_land_rehearses_the_other_active_candidates` | 4376 | PARTIAL | rehearsal_letter 1 次；Engine 的 after_land 归 ⑤i |
| `test_after_land_reports_the_regression_to_the_owner` | 4405 | PARTIAL | 采样没有记到调用（用例换掉了 regression_sweep）；after_land 里的 sweep_window 由 hub-sweep-scenes 的两边互认覆盖；after_land 归 ⑤i |
| `test_exclusive_marks_an_owner_sweep_only_when_head_moves` | 4448 | PARTIAL | mark_owner_moved 2 次、read_owner_sweep 3 次；cmd_exclusive 归 ⑤j |
| `test_owner_commits_get_a_gate_sweep_and_rehearsals` | 4472 | COVERED | hub-sweep：owner_sweep 4 次、mark_owner_moved 2 次、read_owner_sweep 3 次（注入 rehearse_landing 1 次；⑤h1 的部分在 hub-land） |
| `test_landing_waits_for_a_background_gate_sweep` | 4519 | PARTIAL | 不在采样语料里：直接用 sweep_window，由 hub-sweep-scenes 的两边互认覆盖；cmd_exclusive 归 ⑤j |
| `test_background_sweeps_hold_off_other_landings_while_they_run` | 4545 | PARTIAL | owner_sweep 1 次、mark_owner_moved 1 次；Engine 归 ⑤i |
| `test_supervisor_starts_one_owner_sweep_at_a_time` | 4578 | PARTIAL | read_owner_sweep 5 次、mark_owner_moved 1 次；supervisor 归 ⑤j |
| `test_supervisor_counts_runners_left_by_its_previous_generation` | 4652 | PARTIAL | read_owner_sweep 5 次；supervisor 归 ⑤j |
| `test_supervisor_waits_for_a_settled_kernel_before_starting_runners` | 4671 | PARTIAL | read_owner_sweep 4 次；supervisor 归 ⑤j |
| `test_supervisor_stays_while_a_runner_works_without_unread_letters` | 4727 | PARTIAL | read_owner_sweep 4 次；supervisor 归 ⑤j |
| `test_supervisor_stays_while_letters_are_held` | 4767 | PARTIAL | read_owner_sweep 3 次；supervisor 归 ⑤j |
| `test_supervisor_picks_up_runner_json_changes_while_running` | 5002 | PARTIAL | read_owner_sweep 4 次；supervisor 归 ⑤j |
| `test_supervisor_keeps_going_after_a_bad_tick` | 5067 | PARTIAL | read_owner_sweep 2 次；supervisor 归 ⑤j |
| `test_supervisor_stops_restarting_a_crashing_runner` | 5086 | PARTIAL | read_owner_sweep 5 次；supervisor 归 ⑤j |
| `test_owner_sweeps_reinstall_stale_ts_dependencies_under_the_land_lock` | 6979 | COVERED | hub-sweep：ts_install_if_stale 2 次（注入 ts_runner 1 次） |
| `test_a_failed_ts_reinstall_writes_to_the_owner` | 7007 | COVERED | hub-sweep：ts_install_if_stale 3 次（注入 ts_runner 2 次） |
| `test_no_ts_reinstall_while_everything_runs_on_python` | 7031 | COVERED | hub-sweep：ts_install_if_stale 2 次 |
| `test_owner_sweeps_start_with_the_ts_reinstall` | 7043 | COVERED | hub-sweep：owner_sweep 1 次、mark_owner_moved 1 次（注入 ts_install_if_stale 1 次） |

COVERED 10、PARTIAL 15。⑤h1 表里归 ⑤h2 的落地预演与 owner sweep（4221、4274、4293、4324、4472）在这里转 COVERED；Engine 的执行端交付与 after_land（4340、4376、4405、4545）归 ⑤i；supervisor 与 cmd_exclusive（4050、4448、4519、4578、4652、4671、4727、4767、5002、5067、5086）归 ⑤j。

变异：ts/mutations/hub-h2.ts.json 共 75 条（sweep.ts 的 S01–S99，编号有空；clock.ts 的 B01、B02），抓住 73 条，S95、B02 等价。
- 分段跑，先只跑手写场景：
  - 第一段跑到第 62 条时，外部的构建把内存吃紧，被系统停掉；复原留在文件里的那一条、核对锚点之后，接着跑剩下的。
  - 只跑场景时漏掉的 S06、S15、S30、S32、S33、S35、S75、S80、S86、S94，补了场景之后抓住。
  - S15（不带 -rfE）起初当成等价（pytest 9.1.1 的 -r 缺省就是 fE）；themistally-04 指出被管仓库的 pytest 配置可以改 -r，于是在场景的仓库里放了 addopts = -rN 的 pytest.ini。
  - S94 连采样契约也漏掉：语料里没有“收了尾、条件却齐全”的任务。
  - S92、S93 由采样契约抓住。
- B02 等价：计数只在钉住期间加，withPinnedClock 退出时还原，钉住之外一直是 0；只有嵌套钉住才分得出，唯一的调用方不嵌套。
- themistally-04 在新导出的副本上抽查 14 条，抓住 12 条。
  - 抽的是清单里的 S04、S06、S31、S45、S63、S66、S71、S82、S86、S94，与它另加的 Y01–Y04。
  - Y03（预演过只比 head）由采样契约抓住。
  - Y02（挂标记等 .land 用执行端的时限）只是撞上探针的时限，不算断言抓住。
  - Y01、Y04 漏掉。
- 抽查之后的处理：
  - Y04（戳记不查是不是对象）补了数组戳记的场景，由场景抓住。
  - Y02 补了直接调 TS 的时限测试：执行端的时限给 30 秒，用错字段就过不了“10 秒内就抛”。
  - Y01 等价：state.json 只经 canonical_state 写（sort_keys），读回来的任务键本来就排好。
  - 并进清单为 S95–S98，另加 ts 重装那处同类的 S99。
  - 只跑那条直接测试时，S96、S99 都由断言抓住；S97 由采样契约抓住。

## ⑤i 调度循环与 Engine

拆成两片（⑤i 设计稿，themistally-04 复核两轮）：⑤i1 是工人一侧与结项，⑤i2 是选信、协调人一侧与续接。cmd_run 的循环本体归 ⑤j。

用例怎么分到各片，不按测试体里的字面文字挑，而是机械得出：在 kb3 上带追踪跑整份 tests/test_kit_hub.py（299 条、362 个实例），记下每个实例进入过的 kit_hub 函数（按 qualname），以及各片采样器会记到的最外层调用。走到 ⑤i 函数的用例共 106 条：只走 ⑤i1 16 条，⑤i1 与 ⑤i2 都走 51 条，三片都走 5 条，只走 ⑤i2 9 条，⑤i2 加 ⑤j 25 条；另有 23 条只走 ⑤j。

### ⑤i1 工人一侧与结项

做法（⑤i 设计稿第 2–4 节，themistally-04 复核）：
- 采样器给这一片的每个函数都装记录器，只记“同一片的函数不在栈上”的那一次，不挑名单：
  - Engine 的 escalate、worker_job、auto_jev、stage_workspace、verify_delivery、after_delivery、finish_kernel_stage、recheck_exec、worker_turns、redeliver、handle_pass、after_land、after_land_run，以及 land、release_dependents，照 ⑤e2b 的流程函数记；
  - 只读的 output_problem、resumed_session 照 ⑤e2a 记快照。
- Engine 记成仓库与 only_task。它的 runner 在调用期间换成录制包装（内层名 runner），比 prompt 全文、fresh、session_id、retry_of，以及调用当时输入目录里的文件（相对路径与 sha256，按码点排）。
- 用例当时换掉的内层函数照记录注入，另认一组只在 ⑤i 的最外层调用里认的名字（role_prompt、ensure_worktree、apply_candidate、seed_whitebox、run_exec、run_jev、finalize、tidy_finished、regression_sweep、Engine.verify_delivery、Engine.auto_jev）；mkdtemp、run_supervised、sweep_gates、pid_alive 在 ⑤i 的流程函数里总照记录注入。前几片的样本不变。
- 钉住：时刻、信编号（⑤h2 的办法）与 time.time（执行端等不到落地锁时扣信，解除时刻是 int(time.time()) + 120）。
- 随样本带上：名册的改动（overrides）；用例改过的 kit_hub 常量（实测只有 7117 经 inputs_fixture 把 INPUT_FILE_LIMIT 改成 64；TS 只认对得上 deps 的几个，不认的报错）；state 参数读出时的 seen（重放照样建 HubState，save_state 才照三方合并写）；ts 是 state 里的哪一项（ts_alias）；land 收到的是不是用例自己写的假 Engine（4001）。
- 当场核对：传进来的 state 与调用当时的 state.json 是否相同（state_differs）。
- 不重放的：调用当时目录锁有活的持有者（重放时持有者已经不在，接管与否两边不同）；release_dependents 一路不拿也不探锁，不受这条管（themistally-04 定）。
- 带 parametrize 的用例照 pytest 的次序展开成“名[i]”，只认一层、普通的 argvalues。
- 内层抛的 HubError 一族带退出码，重放照真的类抛；rehearse_landing 进了比调用之后 ts 的名单（4376 的假函数写 ts["rehearsal"]）。
- 手写场景用的剧本（request 的 scripted）：照剧本按次交回、不核对参数，每次调用的参数照内层调用记下，随结果交回、三边互比；只给 Python 用例里也换掉的那几个用。剧本的一项可以带 listing：调用当时某个目录下的文件名（按码点排）记进这次调用（为 L01 加的，合入后回归的窗口标记只在窗口开着时在）。

契约：
- hub-engine：72 条用例（4 条带参数的展开成 15 个实例）。
  - 最外层调用 156 次：worker_job 60、resumed_session 52、recheck_exec 6、release_dependents 6、after_land 6、auto_jev 5、stage_workspace 4、verify_delivery 4、after_delivery 4、escalate 3、worker_turns 2、handle_pass 2、land 2。
  - 跳过 1 次：5360 的 worker_job（调用当时 .land 有活的持有者），由手写场景覆盖。
  - 注入：runner 77、role_prompt 77、worktree_root 63、ensure_worktree 48、run_pd 10、Engine.verify_delivery 7、rehearse_landing 7、run_exec 6、run_jev 5、apply_candidate 4、pid_alive 3、Engine.auto_jev 2、finalize 2、revalidate_contract 2、_running_attempts 2、regression_sweep 2、seed_whitebox 2、budget_problems 1、tidy_finished 1、engine.handle_pass 1、engine.after_land 1。
  - state 当场核对标出 11 次（用例把在内存里改过、没存盘的 state 传进去），ts_alias 5 次。
  - 流程函数 103 次、resumed_session 52 次，三边重放都与当时的结果相同（JSON 文字逐字，键的次序也算）。
- hub-engine-scenes：20 条 it。前 6 条是设计稿第 6 节的手写场景（6 组三边对照，“当场重交”的两组在同一条 it 里；另 1 条只测 TS 的时限测试）；接着 13 条是变异第二段之后补的，最后 1 条是 themistally-04 抽查之后补的（Z05），见下面的变异一段。
  - 当场重交：核验没过、同一会话重交一次后通过；重交的回合撞上限流（不扣信、阶段 failed、信里带第一次核验）。
  - 扣信：限流的工人回合；执行端等不到落地锁（另一个进程真拿着 .land，5360 的形状），扣信 120 秒、只记账本不写信、拿到锁之前不建返工版本。
  - 不唤醒工人的信：主任务没登记、有一封缺 type，类型排不了序，照 Python 抛 TypeError（只比类型）。
  - 结项：handle_pass 通过之后放行依赖它的主任务（真 git 取末端）。
  - 只测 TS：另一个进程拿着 .land 时，land 照 landLockWaitSeconds 报“锁被占用：”，不等执行端的 landWaitSeconds。
  - 设计稿第 6 节省掉的两场：战前门禁先退回基线再重交（2559 的 worker_job 一路走到 redeliver，stage_workspace 两次、真 git 26 次；426 的 stage_workspace 真跑退回基线那一支，都在采样里重放上了）；exec-recheck（2661 的 2 次、5152 的 4 次 recheck_exec 都重放上了）。“到点放回扣信”归 ⑤i2 的扣信场景。

| 用例 | 行 | 状态 | TS 契约 |
|---|---|---|---|
| `test_hotfix_rework_records_the_previous_baseline` | 307 | PARTIAL | hub-engine：resumed_session 1 次；coordinator_turn、deliver_coordinator_letter、next_job、step、write_brief 归 ⑤i2 |
| `test_gate_pre_commit_bumps_a_dispatched_contract_and_keeps_the_hotfix_diff` | 373 | COVERED | hub-engine：stage_workspace 1 次 |
| `test_gate_rework_resets_a_worktree_the_state_lost_track_of` | 426 | COVERED | hub-engine：stage_workspace 1 次 |
| `test_first_review_report_must_map_every_dod` | 662 | COVERED | hub-engine：verify_delivery 2 次 |
| `test_candidate_defects_go_to_the_final_review_which_cannot_pass_them` | 993 | COVERED | hub-engine：after_delivery 2 次、verify_delivery 2 次 |
| `test_review_history_survives_rework_and_seals_the_next_round` | 1152 | COVERED | hub-engine：after_delivery 2 次 |
| `test_contract_block_or_executor_conflict_can_send_the_work_upstream` | 1504 | PARTIAL | hub-engine：worker_job 1 次；next_job、step 归 ⑤i2 |
| `test_coordinator_letters_pass_the_guard_before_delivery` | 1639 | PARTIAL | hub-engine：resumed_session 1 次；coordinator_turn、deliver_coordinator_letter、next_job、step、write_brief 归 ⑤i2 |
| `test_three_rejected_coordinator_turns_block_the_task` | 1655 | PARTIAL | hub-engine：resumed_session 3 次、escalate 1 次；coordinator_turn、deliver_coordinator_letter、next_job、step 归 ⑤i2 |
| `test_start_without_brief_is_rejected` | 1669 | PARTIAL | hub-engine：resumed_session 1 次；coordinator_turn、deliver_coordinator_letter、next_job、step 归 ⑤i2 |
| `test_worker_delivery_is_verified_then_forwarded` | 1684 | PARTIAL | hub-engine：worker_job 1 次、resumed_session 1 次；coordinator_turn、deliver_coordinator_letter、next_job、step、write_brief 归 ⑤i2 |
| `test_plan_delivery_must_list_its_external_facts` | 1711 | PARTIAL | hub-engine：worker_job 5 次；next_job、step 归 ⑤i2 |
| `test_plan_with_only_verified_facts_goes_straight_to_the_contract` | 1730 | PARTIAL | hub-engine：worker_job 1 次、resumed_session 1 次；coordinator_turn、deliver_coordinator_letter、next_job、step、write_brief 归 ⑤i2 |
| `test_unverified_external_facts_wait_for_the_owner` | 1745 | PARTIAL | hub-engine：worker_job 1 次；next_job、step 归 ⑤i2；cmd_send、main 归 ⑤j |
| `test_plan_redelivery_replaces_the_external_facts` | 1791 | PARTIAL | hub-engine：worker_job 1 次；next_job、step 归 ⑤i2 |
| `test_worker_turn_with_violation_is_not_delivered` | 1815 | PARTIAL | hub-engine：worker_job 1 次、resumed_session 1 次；coordinator_turn、deliver_coordinator_letter、next_job、step、write_brief 归 ⑤i2 |
| `test_model_api_errors_are_not_retried_and_go_to_the_owner` | 1831 | PARTIAL | hub-engine：worker_job 1 次、resumed_session 1 次；coordinator_turn、deliver_coordinator_letter、next_job、step、write_brief 归 ⑤i2 |
| `test_a_rate_limited_worker_turn_is_held_and_resumed` | 1857 | PARTIAL | hub-engine：worker_job 2 次、resumed_session 1 次；coordinator_turn、deliver_coordinator_letter、letters_held、next_job、runner_may_idle_exit、step、supervisor_busy、write_brief 归 ⑤i2 |
| `test_held_letters_are_dropped_when_the_stage_was_restarted_meanwhile` | 1892 | PARTIAL | hub-engine：worker_job 1 次、resumed_session 1 次；coordinator_turn、deliver_coordinator_letter、next_job、step、write_brief 归 ⑤i2 |
| `test_a_rate_limited_turn_that_also_broke_the_rules_is_not_held` | 1913 | PARTIAL | hub-engine：worker_job 1 次、resumed_session 1 次；coordinator_turn、deliver_coordinator_letter、next_job、step、write_brief 归 ⑤i2 |
| `test_a_stage_left_busy_by_a_killed_runner_is_requeued_and_resumed` | 1946 | PARTIAL | hub-engine：worker_job 1 次；interrupted_letters、next_job、requeue_interrupted、requeue_letters、requeue_task、runner_lock、step、stranded_stages、tasks_with_work 归 ⑤i2 |
| `test_a_resumed_turn_without_a_usable_session_starts_fresh` | 2012 | COVERED | hub-engine：worker_turns 2 次、resumed_session 1 次 |
| `test_a_coordinator_turn_cut_off_by_a_kill_is_requeued_and_resumed` | 2096 | PARTIAL | hub-engine：resumed_session 1 次；coordinator_turn、deliver_coordinator_letter、finished_turn、next_job、requeue_interrupted、requeue_letters、requeue_task、runner_lock、step、stranded_stages、tasks_with_work、write_brief 归 ⑤i2 |
| `test_a_coordinator_turn_that_never_finished_restarts_fresh_and_only_once` | 2122 | PARTIAL | hub-engine：resumed_session 1 次；coordinator_turn、deliver_coordinator_letter、finished_turn、next_job、requeue_interrupted、requeue_letters、requeue_task、runner_lock、step、stranded_stages、write_brief 归 ⑤i2 |
| `test_the_coordinator_marker_is_cleared_on_every_way_out_of_the_turn` | 2150 | PARTIAL | hub-engine：resumed_session 4 次、escalate 1 次；coordinator_turn、fail_stage、next_job、report_step_error、requeue_interrupted、step、stranded_stages 归 ⑤i2 |
| `test_a_jev_cut_off_by_a_kill_is_rerun` | 2187 | PARTIAL | hub-engine：worker_job 1 次；interrupted_letters、next_job、requeue_interrupted、requeue_letters、requeue_task、runner_lock、step、stranded_stages 归 ⑤i2 |
| `test_a_rate_limited_coordinator_turn_is_held_and_resumed` | 2333 | PARTIAL | hub-engine：resumed_session 2 次；coordinator_turn、deliver_coordinator_letter、next_job、step、write_brief 归 ⑤i2 |
| `test_coordinator_api_error_is_not_retried` | 2360 | PARTIAL | hub-engine：escalate 1 次、resumed_session 1 次；coordinator_turn、next_job、step 归 ⑤i2 |
| `test_kernel_runs_jev_right_after_a_passing_delivery` | 2370 | COVERED | hub-engine：auto_jev 5 次 |
| `test_worker_delivery_hands_over_to_the_kernel_jev_only_when_it_passes` | 2395 | PARTIAL | hub-engine：worker_job 2 次、resumed_session 1 次；coordinator_turn、deliver_coordinator_letter、next_job、step、write_brief 归 ⑤i2 |
| `test_a_delivery_that_fails_the_check_is_redone_in_the_same_session` | 2434 | PARTIAL | hub-engine：worker_job 1 次、resumed_session 1 次；coordinator_turn、deliver_coordinator_letter、next_job、step、write_brief 归 ⑤i2 |
| `test_a_redelivery_that_still_fails_goes_to_the_coordinator_saying_so` | 2466 | PARTIAL | hub-engine：worker_job 1 次、resumed_session 1 次；coordinator_turn、deliver_coordinator_letter、next_job、step、write_brief 归 ⑤i2 |
| `test_a_redelivery_may_hand_in_a_block_instead` | 2484 | PARTIAL | hub-engine：worker_job 1 次、resumed_session 1 次；coordinator_turn、deliver_coordinator_letter、next_job、step、write_brief 归 ⑤i2 |
| `test_a_voided_or_rate_limited_redelivery_reports_the_first_check_too` | 2503 | PARTIAL | hub-engine：worker_job 2 次、resumed_session 2 次；coordinator_turn、deliver_coordinator_letter、next_job、step、write_brief 归 ⑤i2 |
| `test_a_contract_that_fails_derive_json_is_redrafted_under_the_same_number` | 2519 | PARTIAL | hub-engine：worker_job 1 次；next_job、step 归 ⑤i2 |
| `test_a_hotfix_gate_redelivery_keeps_the_version_and_the_original_baseline` | 2559 | PARTIAL | hub-engine：worker_job 1 次；next_job、step 归 ⑤i2 |
| `test_a_second_hotfix_rework_keeps_the_original_previous_oracle` | 2607 | PARTIAL | hub-engine：resumed_session 2 次；coordinator_turn、deliver_coordinator_letter、next_job、step、write_brief 归 ⑤i2 |
| `test_exec_recheck_revisits_the_last_attempt_without_rerunning` | 2661 | COVERED | hub-engine：recheck_exec 2 次 |
| `test_owner_takeover_closes_the_task` | 3230 | PARTIAL | hub-engine：release_dependents 1 次；runner_lock 归 ⑤i2；cmd_task_close、task_quiet 归 ⑤j |
| `test_finished_tasks_remove_their_stage_worktrees` | 3276 | PARTIAL | hub-engine：handle_pass 1 次；runner_lock 归 ⑤i2；cmd_task_cleanup、task_quiet 归 ⑤j |
| `test_invalid_output_gets_one_retry` | 3426 | PARTIAL | hub-engine：worker_job 1 次、resumed_session 1 次；coordinator_turn、deliver_coordinator_letter、next_job、step、write_brief 归 ⑤i2 |
| `test_a_timed_out_turn_does_not_use_up_the_format_retry` | 3437 | PARTIAL | hub-engine：worker_job 1 次、resumed_session 1 次；coordinator_turn、deliver_coordinator_letter、next_job、step、write_brief 归 ⑤i2 |
| `test_worker_retries_stop_when_the_output_stays_invalid` | 3455 | PARTIAL | hub-engine：worker_job 3 次、resumed_session 3 次；coordinator_turn、deliver_coordinator_letter、next_job、step、write_brief 归 ⑤i2 |
| `test_the_blocked_letter_says_timed_out_again_only_when_it_did` | 3477 | PARTIAL | hub-engine：worker_job 5 次、resumed_session 5 次；coordinator_turn、deliver_coordinator_letter、next_job、step、write_brief 归 ⑤i2 |
| `test_info_letters_do_not_wake_workers` | 3592 | PARTIAL | hub-engine：worker_job 1 次；next_job、step 归 ⑤i2 |
| `test_rework_starts_a_clean_session` | 3601 | PARTIAL | hub-engine：worker_job 2 次；next_job、step 归 ⑤i2 |
| `test_landing_waits_for_other_tasks_executors` | 4001 | COVERED | hub-engine：land 2 次 |
| `test_exec_delivery_carries_the_rehearsal_and_warns_the_owner` | 4340 | COVERED | hub-engine：worker_job 3 次 |
| `test_after_land_rehearses_the_other_active_candidates` | 4376 | COVERED | hub-engine：after_land 2 次 |
| `test_after_land_reports_the_regression_to_the_owner` | 4405 | COVERED | hub-engine：after_land 3 次 |
| `test_background_sweeps_hold_off_other_landings_while_they_run` | 4545 | COVERED | hub-engine：after_land 1 次 |
| `test_release_moves_the_base_once_every_dependency_is_done` | 4808 | COVERED | hub-engine：release_dependents 3 次 |
| `test_passing_and_owner_close_release_the_dependents` | 4855 | PARTIAL | hub-engine：handle_pass 1 次、release_dependents 1 次；runner_lock 归 ⑤i2；cmd_task_close、main、task_quiet 归 ⑤j |
| `test_owner_adds_a_dependency_found_in_planning` | 4938 | PARTIAL | hub-engine：release_dependents 1 次；runner_lock 归 ⑤i2；cmd_task_after、main、task_quiet 归 ⑤j |
| `test_a_crashed_turn_tells_the_owner_which_letters_were_taken` | 5119 | PARTIAL | hub-engine：resumed_session 1 次；coordinator_turn、fail_stage、next_job、report_step_error、step 归 ⑤i2 |
| `test_exec_recheck_resumes_an_execution_the_hub_was_killed_in` | 5152 | COVERED | hub-engine：recheck_exec 4 次 |
| `test_paused_worker_stage_can_be_started_again` | 5185 | PARTIAL | hub-engine：worker_job 1 次；deliver_coordinator_letter、next_job、step、write_brief 归 ⑤i2 |
| `test_gate_post_workspace_is_seeded_before_the_gate_starts` | 5334 | COVERED | hub-engine：stage_workspace 2 次 |
| `test_exec_waits_for_the_landing_lock_by_holding_its_letter` | 5360 | PARTIAL | hub-engine：worker_job 1 次；另有 worker_job 1 次不重放（调用当时 .land 有活的持有者），由 hub-engine-scenes 的场景覆盖；next_job、step 归 ⑤i2 |
| `test_a_crashed_worker_turn_leaves_the_stage_restartable` | 5390 | PARTIAL | hub-engine：worker_job 1 次；fail_stage、next_job、report_step_error、step 归 ⑤i2 |
| `test_the_gate_hotfix_turn_carries_the_executors_words` | 6622 | PARTIAL | hub-engine：resumed_session 1 次；coordinator_turn、deliver_coordinator_letter、next_job、step、write_brief 归 ⑤i2 |
| `test_a_timed_out_voided_turn_is_resumed_not_restarted` | 6669 | PARTIAL | hub-engine：worker_job 2 次、resumed_session 1 次；coordinator_turn、deliver_coordinator_letter、next_job、step、write_brief 归 ⑤i2 |
| `test_a_voided_turn_that_did_not_time_out_gets_no_resume_hint` | 6695 | PARTIAL | hub-engine：worker_job 1 次、resumed_session 1 次；coordinator_turn、deliver_coordinator_letter、next_job、step、write_brief 归 ⑤i2 |
| `test_the_owners_rework_words_reach_the_reworked_stage_verbatim` | 6712 | PARTIAL | hub-engine：worker_job 1 次、resumed_session 1 次；coordinator_turn、deliver_coordinator_letter、next_job、step、write_brief 归 ⑤i2 |
| `test_each_turn_reads_its_own_copy_and_the_copy_is_gone_afterwards` | 7117 | PARTIAL | hub-engine：worker_job 1 次、resumed_session 1 次；coordinator_turn、deliver_coordinator_letter、next_job、step、write_brief 归 ⑤i2 |
| `test_a_routine_step_the_guard_refuses_goes_to_the_coordinator_with_the_reason` | 7542 | PARTIAL | hub-engine：resumed_session 1 次；coordinator_turn、next_job、route、step 归 ⑤i2 |
| `test_a_batch_that_is_not_routine_tells_the_coordinator_why` | 7559 | PARTIAL | hub-engine：resumed_session 1 次；coordinator_turn、next_job、route、step 归 ⑤i2 |
| `test_the_kernel_leaves_the_last_rework_of_a_stage_to_the_coordinator` | 7574 | PARTIAL | hub-engine：resumed_session 1 次；coordinator_turn、deliver_coordinator_letter、next_job、route、step、write_brief 归 ⑤i2 |
| `test_a_passing_delivery_clears_the_last_check` | 7607 | PARTIAL | hub-engine：worker_job 1 次；next_job、step 归 ⑤i2 |
| `test_a_partly_routed_batch_records_what_went_out` | 7621 | PARTIAL | hub-engine：resumed_session 1 次；coordinator_turn、deliver_coordinator_letter、next_job、route、step、write_brief 归 ⑤i2 |
| `test_a_routing_cut_short_is_handed_back_with_its_own_words` | 7644 | PARTIAL | hub-engine：resumed_session 1 次；coordinator_turn、deliver_coordinator_letter、finished_turn、interrupted_letters、next_job、requeue_letters、requeue_task、step、stranded_stages、write_brief 归 ⑤i2 |
| `test_a_clean_slice_runs_from_task_to_pass_without_a_coordinator_turn` | 7708 | PARTIAL | hub-engine：worker_job 7 次；coordinator_turn、deliver_coordinator_letter、next_job、route、step、write_brief 归 ⑤i2 |

COVERED 16、PARTIAL 56。⑤i1 之后仍 PARTIAL 的，剩下的部分逐条写在上表：step、next_job、coordinator_turn 一族归 ⑤i2，task close、send 一类命令归 ⑤j。前几节写着“归 ⑤i”的 29 条里，这一片关掉 12 条（373、426、662、993、1152、2661、4001、4340、4376、4405、4545、5152），1711、1857、1892、2519、5360、6622、6669、6695、6712 在 ⑤i2 关掉，1745、3276 剩 ⑤j，⑤i2 的 5 条（1564、1985、2029、2205、3985）在下一片；474 那一行是旧的（⑤e2b 表），ensure_worktree 在 ⑤f 表已经 COVERED，这次改掉。

变异：ts/mutations/hub-i1.ts.json 共 150 条（engine.ts），全部抓住，清单里没有判等价的。前 149 条分三段跑，第 150 条来自 themistally-04 的抽查：
- 第一段只跑手写场景（当时的 6 条 it），147 条抓住 29 条。
- 第二段：第一段漏掉的 118 条，用存下的 155 次样本请求让 node 重放，抓住 76 条，漏 42 条。
- 漏掉的 42 条逐条报 themistally-04 定：
  - 41 条补场景，即 hub-engine-scenes 的后 13 条 it。每条造一个让 Python 与变异体走出不同结果的输入，多是采样里没有的情形：
    - 超长的文字（各处截断）；
    - 两条以上的违规与核验问题；
    - 缺 check_ok；
    - 阶段里带 stranded_notice 或 resume；
    - 下游阶段已经交付（作废）；
    - ts 里没有 base_head 或 gate_post：照 Python 只在用到的分支里读（G08、D09）；
    - 后台回归的窗口标记挡着落地（N05）。
  - L01（合入后回归的窗口名）：
    - 我原提议算等价，理由是按主任务号取标记文件的几处都取不到这个名字。
    - themistally-04 指出不等价：landing_blockers 按文件名排序后列出挡路的。"T100-after-land.json" < "T1000.json" < "T100-afterland.json"，改名会让等待说明里两条的先后颠倒。
    - 于是给剧本加了 listing，场景记下回归期间 exec-active 下的文件名。只留这一条 it 单跑时，也是它抓住的。
  - 核查 Y01 时查出 dict() 对列表的报错与 Python 不同：
    - 字符串键的项赋值，Python 报 list indices must be integers or slices, not str；
    - pop(key, None)，Python 报 pop expected at most 1 argument, got 2。
    - 已改成照 Python，新加的两行配 Y03、Y04。
- 第三段：这 44 条（42 条加 Y03、Y04）只跑场景文件，全部抓住。每条都挂在为它写的那条 it 上，没有靠超时的。
- themistally-04 在 0250956 的导出副本上抽查 14 条，抓住 12 条：清单里的 G08、L01，与它另写的 Z01–Z04、Z06–Z09、Z11、Z12。漏掉 2 条：
  - Z05（规划的两类问题换次序）：补了场景（report 为空、又缺 external_facts），并进清单为第 150 条；单跑时只挂这一条 it。
  - Z10（落地后预演别的主任务不排序）：判等价，理由同 ⑤h2 的 Y01：state.json 只经 canonical_state 写（sort_keys），after_land_run 从盘上现读，任务键本来就排好。不进清单。

### ⑤i2 选信、协调人一侧与续接

做法（⑤i 设计稿第 4、5、7 节，themistally-04 复核）：
- 采样器给 ⑤i 两片的全部函数都装记录器，只记最外层，样本只留 ⑤i2 的函数：
  - Engine 的 step、fail_stage、coordinator_turn、route、deliver_coordinator_letter、write_brief，以及 requeue_interrupted、requeue_task、requeue_letters、report_stranded_exec 照流程函数记；
  - 只读的 next_job、finished_turn、interrupted_letters、stranded_stages、letters_held、supervisor_busy、runner_may_idle_exit、tasks_with_work、runner_lock 照快照记（runner_lock 是纯算路径，不存快照）；
  - report_step_error 只在 step 里被调到（它的 exc 参数记不下来）。
- 跳过的收窄（themistally-04 要的）：采样期间给 DirLock.__enter__ 与 lock_alive 各套一层，记下这一次最外层调用拿过或探过的锁；只有“调用当时有活的持有者、又被这次调用碰过”的才跳过。第一版照 ⑤i1 的规则跳过 46 次，多是 cmd_run 自己拿着的 .runner；收窄之后 3 次。⑤i1 中段为 release_dependents 单开的例外由这条通则涵盖，删掉了；⑤i1 的样本不变（156 次，跳过 1 次）。
- DirLock 接管时问的 pid_alive 不录也不注入，两边都用真的（TS 的 DirLock 自己判断，设计稿第 3 节）；用例换掉了 pid_alive、DirLock 又问过它的那次调用不重放，这 90 条里没有。
- 内层名单加 release_held（4778 的 hold_until_called 换掉它，step 每一步先调）；参数里一组路径（paths）照方法的参数位置转回 Path；调用之后的元组参数也比（requeue_interrupted 的 skip）；采样器另认 capsys（1 条用例要）。
- 回合出意外那封信的比法（设计稿第 7 节，themistally-04 定的四个条件）：
  - 只认内核发给站主的“阻塞”信、摘要以“<agent> 的回合出了意外”开头；
  - “偏离”只比最后一行，开头的“kit_hub.”去掉：用例 import kit_hub，生产上 kit_hub 当脚本跑（__main__），TS 照生产写；
  - 账本里这封信的 letter.delivered 事件，sha256 换成占位；改写了哪些 msg_id 一起比，封数或 msg_id 不同就算不同；
  - 只写一个函数（engine-fixtures 的 crashNormalized），三份输出都过它；其余照旧逐字比。TS 写的类名另由只测 TS 的断言守。

契约：
- hub-step：90 条用例（带参数的 4 条展开成 15 个实例）。
  - ⑤i2 的最外层调用 563 次：runner_lock 264、step 127、requeue_interrupted 62、tasks_with_work 40、supervisor_busy 39、deliver_coordinator_letter 8、interrupted_letters 7、runner_may_idle_exit 7、fail_stage 3、next_job 3、letters_held 2、requeue_task 1。
  - 跳过 3 次：requeue_interrupted 2 次（用例在进程里拿着 .runners/T001），由 hub-step-scenes 的 runner 锁场景覆盖；step 1 次（5360，.land），由 ⑤i1 的场景与本片的到点放回场景覆盖。
  - 注入：role_prompt 126、runner 126、worktree_root 114、ensure_worktree 99、Engine.verify_delivery 7、run_pd 6、release_held 3、run_exec 3、run_jev 3、Engine.auto_jev 2、rehearse_landing 2、revalidate_contract 2、apply_candidate 2、budget_problems 1、pid_alive 1、seed_whitebox 1。
  - state 当场核对标出 5 次，都是 1564 的 deliver_coordinator_letter。
  - 流程函数 198 次、只读的 362 次，三边重放都与当时的结果相同。
- hub-step-scenes：16 条 it，15 条三边对照，1 条只测 TS。前 5 条是本片原有的：
  - 续接：另一个进程（真的 Python 子进程）拿着 .runners/T001 时 requeue_interrupted 不动、一个文件都不写；另配没人拿锁的对照，照常放回。
  - 扣信：限流的协调人回合扣信、在办标记清掉；到点放回：协调人的信放回后接着起回合（解除时刻正好等于钉住的时刻，另配晚 1 秒的对照）；执行端的信放回后阶段从 paused 回到 assigned、接着跑执行端（5360 的形状）。
  - 场景先 hub.ensure()：new 目录不在时 os.rename 报 OSError，会被当成“别人已经放回了”吞掉。
  - 只测 TS：回合出意外那封信“偏离”的最后一行照生产写类名（HubError 不带模块名，DispatchError 带 pi_dispatch.）；账本里 step.error 的 error 只写类名（X07，补 themistally-04 的抽查）。
  - 后 9 条是变异补的（见下面的变异一段），每条 it 的标题写了对着哪几条变异，全是三边对照：
    - 回合出意外：信都读不出主任务、出错文字为空、400 字的出错文字、20 封信；
    - 协调人的信：没登记的主任务、不是进行中的主任务、同时有两个主任务的信、回合进行中的在办标记；
    - 协调人回合作废：限流又带两条违规、两次都没有输出；
    - 拒收：头部缺几样、正文 40 行与 41 行、续接回合里因格式拒收、1600 字的类型；不是对象的信直接调 deliver_coordinator_letter；
    - 内核代办：执行端第三次返工照样代办；
    - 续接：扣着的信、续接过的是别的信、700 字的回合号、cur 里读不出信头的信、blocked 主任务直接调 requeue_task；
    - 执行端被打断：pid_alive 问不出死活、attempt 跑完没结论、15 封信；
    - 只读的：next_job、tasks_with_work，finished_turn 直接调；
    - 内核代办投信那一刻的在办标记。
  - 最后 2 条补 themistally-04 的抽查（见下面的变异一段，X08–X11），三边对照：
    - 协调人的信：一栏只有空白；执行端报过合同矛盾时返工合同端；
    - 续接：协调人的信放回过一次又被收掉、同时有停住的工人阶段；同一阶段重新开工之前读掉的旧信还在 cur。
  - 探针为这批场景加了两样，两边对称：
    - 剧本一项可以带 peek：调用当时读一个文件，记进这次调用。C06 用它在 runner 被调的那一刻读 state.json。
    - 请求可以带 peek_deliver：每次投信那一刻读一个文件，结果里交回 deliver_peeks。T06 用它看代办途中的在办标记。Python 在类上包 Hub.deliver，请求末尾照 saved 还原（投信抛错也还原）；TS 包这次请求的 hub 实例。
  - 场景辅助：tasksScene（state.json 里放几个主任务），engine-fixtures 的 letter 加 extra（另加的栏，如审计端的“结论”）。
- hub-quiesce：跑到静止（设计稿第 5 节）。
  - 两边探针各有一个流程名 quiesce，照 cmd_run 的串行次序驱动，这段次序抄自 cmd_run，⑤j 换成真的 cmd_run 之后删掉：串行时先 requeue_interrupted；exec-step 的未读信里有“通过”就取第一封 land，挡路就停；否则 step，交回 False 时照 cmd_run 问 runner_may_idle_exit，还有扣着的信就接着走（themistally-04 同意）；land 也算一步，最多 80 步。每一步钉基准加 i+1 秒，信编号从头编。
  - 剧本由 TS 一侧按种子生成（quiesce-script.ts，mulberry32）：回合按 agent 分开；协调人的“开工”照阶段次序推进，其余从“返工、发错收件人、不附 brief、输出作废、什么都不发”里抽；工人从“合格交付、违规、格式错、超时、限流（80 秒内解除）、接口报错、阻塞信”里抽；内层函数对 ts 的改动写成键路径加新值（ts_set），两边只照着套用。
  - 初始信箱：T001 已经走到结项、exec-step 有一封“通过”；T002 依赖 T001、规划已交付。
  - 种子 1–30，每批 5 个，三边逐字相同（每一步做了什么、跑完时的信箱与 tasks 下的文件、state.json、账本、git 状态、runner 的调用序列）。契约另核对确实走到了：每个种子第一步都是 land、都放行了 T002；扣信与到点放回、内核代办、回合出意外、JEV 自动跑、当场重交都至少有一个种子走到。
  - 与生产不同的一点：时刻钉住之后，同一步里投出的几封信时刻相同，在同一个信箱里按发件人别名排序，而不是按投递先后。

| 用例 | 行 | 状态 | TS 契约 |
|---|---|---|---|
| `test_owner_can_order_a_rework_before_the_first_review` | 261 | PARTIAL | hub-step：deliver_coordinator_letter 1 次；cmd_send、main 归 ⑤j |
| `test_hotfix_rework_records_the_previous_baseline` | 307 | COVERED | hub-step：step 1 次 |
| `test_runner_exits_between_steps_once_the_kernel_changes` | 1027 | PARTIAL | hub-step：requeue_interrupted 1 次、runner_lock 1 次；cmd_run、configured_parallel 归 ⑤j |
| `test_runner_restarts_on_committed_kernel_changes` | 1082 | PARTIAL | hub-step：requeue_interrupted 2 次、runner_lock 2 次；cmd_run、configured_parallel 归 ⑤j |
| `test_contract_block_or_executor_conflict_can_send_the_work_upstream` | 1504 | COVERED | hub-step：step 1 次 |
| `test_stage_reworks_are_capped` | 1564 | COVERED | hub-step：deliver_coordinator_letter 5 次 |
| `test_coordinator_letters_pass_the_guard_before_delivery` | 1639 | COVERED | hub-step：step 1 次 |
| `test_three_rejected_coordinator_turns_block_the_task` | 1655 | COVERED | hub-step：step 4 次 |
| `test_start_without_brief_is_rejected` | 1669 | COVERED | hub-step：step 1 次 |
| `test_worker_delivery_is_verified_then_forwarded` | 1684 | COVERED | hub-step：step 2 次 |
| `test_plan_delivery_must_list_its_external_facts` | 1711 | COVERED | hub-step：step 5 次 |
| `test_plan_with_only_verified_facts_goes_straight_to_the_contract` | 1730 | COVERED | hub-step：step 2 次 |
| `test_unverified_external_facts_wait_for_the_owner` | 1745 | PARTIAL | hub-step：step 1 次；cmd_send、main 归 ⑤j |
| `test_plan_redelivery_replaces_the_external_facts` | 1791 | COVERED | hub-step：step 1 次 |
| `test_worker_turn_with_violation_is_not_delivered` | 1815 | COVERED | hub-step：step 2 次 |
| `test_model_api_errors_are_not_retried_and_go_to_the_owner` | 1831 | COVERED | hub-step：step 2 次 |
| `test_a_rate_limited_worker_turn_is_held_and_resumed` | 1857 | COVERED | hub-step：step 4 次、supervisor_busy 4 次、runner_may_idle_exit 3 次、letters_held 2 次 |
| `test_held_letters_are_dropped_when_the_stage_was_restarted_meanwhile` | 1892 | COVERED | hub-step：step 2 次 |
| `test_a_rate_limited_turn_that_also_broke_the_rules_is_not_held` | 1913 | COVERED | hub-step：step 2 次 |
| `test_supervisor_puts_due_letters_back_and_starts_their_runner` | 1925 | PARTIAL | hub-step：requeue_interrupted 1 次、tasks_with_work 1 次；pause_requested、supervise_tick 归 ⑤j |
| `test_a_stage_left_busy_by_a_killed_runner_is_requeued_and_resumed` | 1946 | COVERED | hub-step：requeue_interrupted 4 次、step 2 次、tasks_with_work 2 次、runner_lock 1 次；另有 requeue_interrupted 1 次不重放（调用当时有活的持有者：.runners/T001），由手写场景覆盖 |
| `test_a_turn_killed_midway_restarts_in_a_new_session_and_is_requeued_only_once` | 1985 | COVERED | hub-step：requeue_interrupted 3 次 |
| `test_requeue_leaves_unread_and_kernel_run_stages_alone` | 2029 | COVERED | hub-step：requeue_interrupted 1 次 |
| `test_supervisor_requeues_only_tasks_nobody_is_working_on` | 2057 | PARTIAL | hub-step：requeue_interrupted 2 次、tasks_with_work 2 次；pause_requested、supervise_tick 归 ⑤j |
| `test_a_coordinator_turn_cut_off_by_a_kill_is_requeued_and_resumed` | 2096 | COVERED | hub-step：step 2 次、requeue_interrupted 1 次、runner_lock 1 次、tasks_with_work 1 次；另有 requeue_interrupted 1 次不重放（调用当时有活的持有者：.runners/T001），由手写场景覆盖 |
| `test_a_coordinator_turn_that_never_finished_restarts_fresh_and_only_once` | 2122 | COVERED | hub-step：requeue_interrupted 2 次、step 1 次 |
| `test_the_coordinator_marker_is_cleared_on_every_way_out_of_the_turn` | 2150 | COVERED | hub-step：step 4 次、requeue_interrupted 1 次 |
| `test_a_jev_cut_off_by_a_kill_is_rerun` | 2187 | COVERED | hub-step：step 1 次、requeue_interrupted 1 次 |
| `test_a_stranded_exec_stage_is_reported_to_the_owner_once` | 2205 | COVERED | hub-step：requeue_interrupted 3 次 |
| `test_interrupted_letters_reads_the_ledger_from_the_assignment_on` | 2279 | COVERED | hub-step：interrupted_letters 7 次 |
| `test_a_rate_limited_coordinator_turn_is_held_and_resumed` | 2333 | COVERED | hub-step：step 2 次 |
| `test_coordinator_api_error_is_not_retried` | 2360 | COVERED | hub-step：step 1 次 |
| `test_worker_delivery_hands_over_to_the_kernel_jev_only_when_it_passes` | 2395 | COVERED | hub-step：step 3 次 |
| `test_a_delivery_that_fails_the_check_is_redone_in_the_same_session` | 2434 | COVERED | hub-step：step 2 次 |
| `test_a_redelivery_that_still_fails_goes_to_the_coordinator_saying_so` | 2466 | COVERED | hub-step：step 2 次 |
| `test_a_redelivery_may_hand_in_a_block_instead` | 2484 | COVERED | hub-step：step 2 次 |
| `test_a_voided_or_rate_limited_redelivery_reports_the_first_check_too` | 2503 | COVERED | hub-step：step 4 次 |
| `test_a_contract_that_fails_derive_json_is_redrafted_under_the_same_number` | 2519 | COVERED | hub-step：step 1 次 |
| `test_a_hotfix_gate_redelivery_keeps_the_version_and_the_original_baseline` | 2559 | COVERED | hub-step：step 1 次 |
| `test_a_second_hotfix_rework_keeps_the_original_previous_oracle` | 2607 | COVERED | hub-step：step 2 次 |
| `test_owner_takeover_closes_the_task` | 3230 | PARTIAL | hub-step：runner_lock 10 次；cmd_task_close、lock_alive、task_quiet 归 ⑤j |
| `test_finished_tasks_remove_their_stage_worktrees` | 3276 | PARTIAL | hub-step：runner_lock 20 次；cmd_task_cleanup、lock_alive、task_quiet 归 ⑤j |
| `test_invalid_output_gets_one_retry` | 3426 | COVERED | hub-step：step 2 次 |
| `test_a_timed_out_turn_does_not_use_up_the_format_retry` | 3437 | COVERED | hub-step：step 2 次 |
| `test_worker_retries_stop_when_the_output_stays_invalid` | 3455 | COVERED | hub-step：step 6 次 |
| `test_the_blocked_letter_says_timed_out_again_only_when_it_did` | 3477 | COVERED | hub-step：step 10 次 |
| `test_info_letters_do_not_wake_workers` | 3592 | COVERED | hub-step：step 1 次 |
| `test_rework_starts_a_clean_session` | 3601 | COVERED | hub-step：step 2 次 |
| `test_task_runner_only_takes_its_own_task_letters` | 3985 | COVERED | hub-step：next_job 3 次、tasks_with_work 2 次 |
| `test_supervisor_runs_one_runner_per_task_up_to_the_limit` | 4050 | PARTIAL | hub-step：requeue_interrupted 5 次、supervisor_busy 5 次、tasks_with_work 5 次、runner_lock 2 次；cmd_run、configured_parallel、owner_sweep_tick、pause_requested、supervise、supervise_tick 归 ⑤j |
| `test_serial_runner_refuses_while_task_runners_are_alive` | 4106 | PARTIAL | hub-step：runner_lock 2 次；cmd_run、configured_parallel、lock_alive 归 ⑤j |
| `test_task_runner_exits_for_the_supervisor_on_kernel_changes` | 4118 | PARTIAL | hub-step：runner_lock 3 次；cmd_run、lock_alive 归 ⑤j |
| `test_supervisor_counts_runners_left_by_its_previous_generation` | 4652 | PARTIAL | hub-step：requeue_interrupted 5 次、supervisor_busy 5 次、tasks_with_work 5 次、runner_lock 3 次；cmd_run、configured_parallel、lock_alive、owner_sweep_tick、pause_requested、supervise、supervise_tick 归 ⑤j |
| `test_supervisor_waits_for_a_settled_kernel_before_starting_runners` | 4671 | PARTIAL | hub-step：requeue_interrupted 4 次、supervisor_busy 4 次、tasks_with_work 4 次、runner_lock 2 次；cmd_run、configured_parallel、owner_sweep_tick、pause_requested、supervise、supervise_tick 归 ⑤j |
| `test_supervisor_ticks_the_owner_sweep_every_round` | 4679 | PARTIAL | hub-step：requeue_interrupted 2 次、runner_lock 2 次、supervisor_busy 2 次、tasks_with_work 2 次；cmd_run、configured_parallel、pause_requested、supervise、supervise_tick 归 ⑤j |
| `test_status_shows_the_parallel_runners` | 4689 | PARTIAL | hub-step：runner_lock 1 次；cmd_status、configured_parallel、lock_alive 归 ⑤j |
| `test_supervisor_stays_while_a_runner_works_without_unread_letters` | 4727 | PARTIAL | hub-step：requeue_interrupted 4 次、supervisor_busy 4 次、runner_lock 3 次；cmd_run、configured_parallel、lock_alive、owner_sweep_tick、supervise、supervise_tick 归 ⑤j |
| `test_supervisor_stays_while_letters_are_held` | 4767 | PARTIAL | hub-step：requeue_interrupted 3 次、supervisor_busy 3 次、tasks_with_work 3 次、runner_lock 2 次；cmd_run、configured_parallel、owner_sweep_tick、pause_requested、supervise、supervise_tick 归 ⑤j |
| `test_serial_hub_stays_while_letters_are_held` | 4776 | PARTIAL | hub-step：step 3 次、runner_may_idle_exit 3 次、requeue_interrupted 1 次、runner_lock 1 次；cmd_run、configured_parallel 归 ⑤j |
| `test_serial_hub_requeues_interrupted_stages_when_it_starts` | 4783 | PARTIAL | hub-step：step 1 次、runner_lock 1 次、runner_may_idle_exit 1 次；cmd_run、configured_parallel 归 ⑤j |
| `test_passing_and_owner_close_release_the_dependents` | 4855 | PARTIAL | hub-step：runner_lock 5 次；cmd_task_close、lock_alive、main、task_quiet 归 ⑤j |
| `test_owner_commands_only_need_the_task_lock_under_a_supervisor` | 4882 | PARTIAL | hub-step：runner_lock 24 次；lock_alive、task_quiet 归 ⑤j |
| `test_owner_rebases_a_task_before_its_contract_starts` | 4903 | PARTIAL | hub-step：runner_lock 30 次；cmd_task_rebase、lock_alive、main、task_quiet 归 ⑤j |
| `test_owner_adds_a_dependency_found_in_planning` | 4938 | PARTIAL | hub-step：runner_lock 45 次；cmd_task_after、lock_alive、main、task_quiet 归 ⑤j |
| `test_tasks_others_wait_for_get_runners_first` | 4984 | COVERED | hub-step：tasks_with_work 2 次 |
| `test_supervisor_picks_up_runner_json_changes_while_running` | 5002 | PARTIAL | hub-step：requeue_interrupted 4 次、supervisor_busy 4 次、tasks_with_work 4 次、runner_lock 2 次；cmd_run、configured_parallel、owner_sweep_tick、pause_requested、supervise、supervise_tick 归 ⑤j |
| `test_supervisor_restart_keeps_where_parallel_came_from` | 5035 | PARTIAL | hub-step：runner_lock 4 次；cmd_run、configured_parallel、supervise 归 ⑤j |
| `test_supervisor_keeps_going_after_a_bad_tick` | 5067 | PARTIAL | hub-step：requeue_interrupted 3 次、supervisor_busy 3 次、runner_lock 2 次、tasks_with_work 2 次；cmd_run、configured_parallel、owner_sweep_tick、pause_requested、supervise、supervise_tick 归 ⑤j |
| `test_supervisor_stops_restarting_a_crashing_runner` | 5086 | PARTIAL | hub-step：requeue_interrupted 5 次、supervisor_busy 5 次、tasks_with_work 5 次、runner_lock 2 次；cmd_run、configured_parallel、owner_sweep_tick、pause_requested、supervise、supervise_tick 归 ⑤j |
| `test_a_crashed_turn_tells_the_owner_which_letters_were_taken` | 5119 | COVERED | hub-step：step 1 次 |
| `test_paused_worker_stage_can_be_started_again` | 5185 | COVERED | hub-step：deliver_coordinator_letter 1 次、step 1 次 |
| `test_exec_waits_for_the_landing_lock_by_holding_its_letter` | 5360 | COVERED | hub-step：step 1 次；另有 step 1 次不重放（调用当时有活的持有者：.land），由手写场景覆盖 |
| `test_a_crashed_worker_turn_leaves_the_stage_restartable` | 5390 | COVERED | hub-step：fail_stage 3 次、step 1 次 |
| `test_owner_unsticks_a_stage_nobody_is_working_on` | 5425 | PARTIAL | hub-step：runner_lock 30 次；cmd_task_unstick、lock_alive、task_quiet 归 ⑤j |
| `test_owner_raises_the_attempt_budget` | 6223 | PARTIAL | hub-step：runner_lock 45 次；cmd_task_budget、lock_alive、task_quiet 归 ⑤j |
| `test_owner_commands_pause_a_busy_task_runner` | 6346 | PARTIAL | hub-step：runner_lock 18 次、requeue_interrupted 2 次；cmd_run、lock_alive、pause_requested、supervise_tick、task_quiet 归 ⑤j |
| `test_the_gate_hotfix_turn_carries_the_executors_words` | 6622 | COVERED | hub-step：step 1 次 |
| `test_a_timed_out_voided_turn_is_resumed_not_restarted` | 6669 | COVERED | hub-step：step 3 次 |
| `test_a_voided_turn_that_did_not_time_out_gets_no_resume_hint` | 6695 | COVERED | hub-step：step 2 次 |
| `test_the_owners_rework_words_reach_the_reworked_stage_verbatim` | 6712 | COVERED | hub-step：step 2 次 |
| `test_each_turn_reads_its_own_copy_and_the_copy_is_gone_afterwards` | 7117 | COVERED | hub-step：step 2 次 |
| `test_the_kernel_routes_a_routine_batch_without_waking_the_coordinator` | 7524 | COVERED | hub-step：step 1 次 |
| `test_a_routine_step_the_guard_refuses_goes_to_the_coordinator_with_the_reason` | 7542 | COVERED | hub-step：step 1 次 |
| `test_a_batch_that_is_not_routine_tells_the_coordinator_why` | 7559 | COVERED | hub-step：step 1 次 |
| `test_the_kernel_leaves_the_last_rework_of_a_stage_to_the_coordinator` | 7574 | COVERED | hub-step：step 2 次 |
| `test_a_passing_delivery_clears_the_last_check` | 7607 | COVERED | hub-step：step 1 次 |
| `test_a_partly_routed_batch_records_what_went_out` | 7621 | COVERED | hub-step：step 1 次 |
| `test_a_routing_cut_short_is_handed_back_with_its_own_words` | 7644 | COVERED | hub-step：deliver_coordinator_letter 1 次、step 1 次、requeue_task 1 次 |
| `test_an_audit_return_is_routed_with_the_blockers` | 7668 | COVERED | hub-step：step 1 次 |
| `test_a_clean_slice_runs_from_task_to_pass_without_a_coordinator_turn` | 7708 | COVERED | hub-step：step 15 次 |

COVERED 60、PARTIAL 30（再加只走 ⑤i1 的 16 条，⑤i 共 COVERED 76，同设计稿第 8 节）。PARTIAL 的 30 条剩下的部分归 ⑤j（cmd_run 的循环本体、cmd_send、supervise、task_quiet 一类），逐条写在上表。⑤i1 之后剩 ⑤i2 的 9 条（1711、1857、1892、2519、5360、6622、6669、6695、6712）与只走 ⑤i2 的 5 条（1564、1985、2029、2205、3985）在这里转 COVERED；1745、3276 剩 ⑤j。

变异：ts/mutations/hub-i2.ts.json 共 107 条（engine.ts 与 requeue.ts），抓住 106 条，X03 判等价。前 102 条分四段跑，后 5 条补 themistally-04 的抽查：
- 第一段只跑手写场景（当时的 5 条 it），抓住 7 条。
- 第二段：第一段漏掉的 95 条，用存下的 560 次样本请求让 node 重放，抓住 62 条，漏 33 条。
- 第三段：这 33 条只跑 hub-quiesce（30 份剧本），抓住 C20（没有拒收时拒收计数清零），漏 32 条。
- 漏掉的 32 条逐条报 themistally-04 定，每条附改了哪一行、样本与剧本为什么走不到。样本里各条要的情形逐条数过：
  - 截断长度 6 条（R04、R05、R06、C21、Q16、Q26）：样本里这几处的文字最长分别是 34、43、66、142、43 字，离截断（200 与 300、600、1500、600、600）都远；剧本的各栏只有一两个词。照 themistally-04 的规矩，补长文字的场景，不判等价。
  - 走不到的分支：剧本只有两个已登记的主任务，runner 从不被收掉（没有残留的在办标记，续接一族走不到），协调人的作废回合只带一条违规、从不限流；样本里也一次都没有这些情形：同时有两个主任务的信、两条违规、正文 40 或 41 行、一封信几处格式问题、续接回合里的拒收、执行端第三次返工、扣着的信又在在办标记里。
  - 三条只在进程死掉时看得到：
    - D01（不是对象的信的拒收原因）：Python 的 coordinator_turn 拒收时要取 item.get，不是对象的信自己先崩，只有直接调 deliver_coordinator_letter 看得到。
    - C06（协调人回合的在办标记带 at）：标记写进 ts 后、调 runner 之前就存盘（kit_hub.py:5092–5094），三个出口与 report_step_error 都会清掉，step 交回后看不到。剧本加 peek，在 runner 被调的那一刻读 state.json。标记不带 at 的后果：requeue_task 拿标记的 at 当 since（kit_hub.py:4867），since 成了空串，finished_turn 会认这一回合开始之前跑完的回合，续接记下的回合号就错了。
    - T06（内核代办的在办标记带 routing）：代办的标记同样在投信前存盘（kit_hub.py:5182–5183），requeue_task 据它的 routing 把续接记成代办。探针加 peek_deliver，在投信那一刻读 state.json，三边比。
  - 两条生产里走不到，补直接调用：
    - Q01（finished_turn 严格大于 since）：真回合号是“开始时刻-随机后缀”（kit_hub.py:1977，TS 的 TurnRunner 同），标记的 at 不带后缀，turn_id 不可能恰好等于 since。
    - Q12（requeue_task 先核主任务是不是进行中）：requeue_task 只有 requeue_interrupted 一个调用方（kit_hub.py:4845），进锁前已经筛过状态；进锁后再核一次，是防筛完到拿锁之间状态变了。
  - Q11（拿不到锁之外的 HubError 照样抛）：cur 里一封读不出信头的信，parse_letter 抛 HubError（kit_hub.py:683，code 是缺省的 EXIT_FAIL），抛在 runner 锁里面。
  - X03 判等价，同 ⑤i1 的 Z10（themistally-04 同意）：requeue_interrupted 每次从盘上新读 state.json（kit_hub.py:4840），盘上只由 canonical_state 写、键已按码点排好，再排一次不改次序。清单里这条标了 equivalent，写明前提。
- 第四段：其余 31 条按“该由哪条 it 抓住”分 9 组，每组用 vitest -t 只跑那一条 it（每组的基准都是 1 passed、13 skipped），全部抓住。都是三边对照比出的不同，没有靠超时的。
- 抽查：themistally-04 在 d0684dd 上另写 15 条（engine.ts 9 条、requeue.ts 6 条），抓住 10 条。漏的 5 条它都对过 Python，都是真缺口、没有等价的；各补一个场景，照原样加进清单（X07–X11），按 it 分 3 组用 vitest -t 跑（每组的基准都是 1 passed、15 skipped），全部抓住，没有靠超时的：
  - X07（抽查 W02，step.error 的 error 写成带模块的类名）：Python 写 type(exc).__name__（kit_hub.py:5037）。只有别的模块的类两样写法不同（DispatchError 与 pi_dispatch.DispatchError），HubError 相同。只测 TS 那条 it 加看账本。
  - X08（抽查 W06，协调人信的各栏不去首尾空白）：render_letter 本来就去空白（kit_hub.py:672），只有整栏是空白时不同：Python 写成“无”照投，变异后 letter_errors 报正文缺这一栏、拒收。场景：协调人一封汇报的“偏离”是三个空格。
  - X09（抽查 W07，热修补不看是不是门禁前）：_guard_rework 见阶段 failed 就放行（kit_hub.py:1078），返工门禁前以外的阶段也会走到热修补那一句（kit_hub.py:5225）。场景：执行端报了 2 条合同矛盾、合同端核验没过，协调人返工合同端，不起热修补。
  - X10（抽查 V01，协调人不再续接后照样处理阶段）：requeue_letters 不再续接时把主任务转 blocked，requeue_task 处理阶段之前重新看状态（kit_hub.py:4873）。场景：协调人那批信放回过一次又被收掉，同时有一个停住的工人阶段：主任务转 blocked，阶段不动，工人的信留在 cur。
  - X11（抽查 V02，阶段的起点不用 assigned_at）：同一阶段重新开工之前读掉的旧信还在 cur 时才不同（kit_hub.py:4876）。场景：旧开工信在 assigned_at 之前读掉、新信在之后读掉，只放回新信。

### ⑤j1 站主命令

做法（⑤j 设计稿第 1–3 节，themistally-04 复核设计、中段与移植）：
- ⑤j 拆成三片：j1 站主命令，j2 进程模型（cmd_run、supervisor、exclusive、内核文件指纹），j3 转交（kit_hub.py 的 main 照选择文件转交 TS）。argparse 与 main 留在 Python 到第 ⑥ 步，命令接启动器交来的 pyargs（键同 argparse 的 Namespace）。
- 采样器给 13 个站主命令装流程记录器：cmd_init、cmd_task_new、close、rebase、after、unstick、budget、cleanup、cmd_send、cmd_exec_recheck、cmd_take、cmd_status、cmd_metrics。只读的 uncommitted_references、turn_metrics、exec_metrics、configured_parallel、recorded_sum 照快照记。只记最外层。
  - 命令的参数记成仓库与 Namespace 去掉 func 后的各键；仓库照 args.repo 用 pd.Repo.discover 找（同 find_repo，不经它的记录器）。
  - 调用期间另记读到的标准输入与写出的 stdout、stderr，三边一起比；重放时标准输入给记下的文字。
  - --file、--brief 指向的文件照调用当时的字节记下，重放前写回（6579 先写 2001 字、再把同一个文件写短）；记录器要求它们是绝对路径。
  - 仓库外的目录（attempt 的 meta.json 记的 worktree、state 里各 workspaces 记的路径）：在的随快照存；不在的记成 absent，重放前删掉。3276 在 cleanup 之后又建了同一个 wt-attempt-001；第三次 cleanup 前删掉的 not-a-worktree 又被上一次重放的快照放回来，两处都实测过。只删用例临时目录（仓库的上一层）下的，别处报错；用例手搭的相对路径占位不算。
  - lock_alive、supervisor_alive、pause_marker、find_repo、task_quiet 不单记：前两个看 pid 死活，task_quiet 是上下文管理器。它们随命令比，pid_alive 照记录注入；用例直接用它们的几处由手写场景覆盖。
- 用例清单由 scratchpad 的 j1_tests.py 从 i_trace2.json 机械得出：走到这 18 个函数的 35 条。configured_parallel 中段挪进这一片（cmd_status 调它），4094 跟着归到 j1。

契约：
- hub-commands：35 条用例，最外层调用 146 次：configured_parallel 69、cmd_send 20、task_after 10、task_budget 10、task_unstick 8、task_new 7、task_rebase 7、task_close 6、task_cleanup 4、exec_metrics 2、cmd_status 1、cmd_metrics 1、turn_metrics 1。
  - 跳过 1 次：4689 的 status（用例自己拿着 .runners/T002），由手写场景覆盖。
  - 注入：run_pd 4、pid_alive 2、contract_requirements 1、tidy_finished 1。
  - 站主命令 73 次、只读的 72 次，三边重放都与当时的结果逐字相同（交回值、文件、账本、git 状态、stdout、stderr）。
- hub-commands-scenes：16 条 it，全部三边对照。
  - 前 5 条补采样走不到的：整份测试里没有用例调的 init、take、exec-recheck；status 时另一个进程（真的 Python 子进程）拿着锁（补跳过的那一次），连同 owner.json 的几种写法（读不出、不是 UTF-8、持有者已退出）与 runner.json 的几种写法（坏 JSON、"x"、UTF-16 带 BOM）；task_quiet：主任务的锁有活的持有者时先打印再等，supervisor 拿着总锁时只等主任务的锁。
  - 中间 8 条是变异补的（见下面的变异一段），每条 it 的标题写了对着哪几条变异；最后 3 条补 themistally-04 的抽查（S05、S08–S11）。
- 复核时改的两处（themistally-04 实测）：lock_alive、configured_parallel 照 Python 的 except ValueError，也接住 read_text 读到不是 UTF-8 的文件时的 UnicodeDecodeError（PowerShell 5.1 的 Out-File 与 > 缺省写 UTF-16）；cmd_send 读标准输入时留下开头的 UTF-8 BOM（Python 的 utf-8 不去它，TextDecoder 要带 ignoreBOM）。
- 接受的两处不同（themistally-04 复核时定，计划第 10 节）：坏台账上 strptime 与不是文字的 at 的报错文字不细分；sorted(set(...)) 全是同一种非文字的值时不排。

| 用例 | 行 | 状态 | TS 契约 |
|---|---|---|---|
| `test_owner_can_order_a_rework_before_the_first_review` | 261 | COVERED | hub-commands：cmd_send 4 次 |
| `test_runner_exits_between_steps_once_the_kernel_changes` | 1027 | PARTIAL | hub-commands：configured_parallel 1 次；cmd_run、code_fingerprint、kernel_files、kernel_settled、refuse_dirty_kernel 归 ⑤j2 |
| `test_runner_restarts_on_committed_kernel_changes` | 1082 | PARTIAL | hub-commands：configured_parallel 2 次；cmd_run、kernel_settled、refuse_dirty_kernel 归 ⑤j2 |
| `test_unverified_external_facts_wait_for_the_owner` | 1745 | COVERED | hub-commands：cmd_send 3 次 |
| `test_supervisor_puts_due_letters_back_and_starts_their_runner` | 1925 | PARTIAL | 这条走到的 ⑤j1 函数（pause_marker）没有单独记下的调用：task_quiet、lock_alive 一类不单记，或只在 ⑤j2 的函数里面被调；到 ⑤j2 一起比；pause_requested、supervise_tick 归 ⑤j2 |
| `test_supervisor_requeues_only_tasks_nobody_is_working_on` | 2057 | PARTIAL | 这条走到的 ⑤j1 函数（pause_marker）没有单独记下的调用：task_quiet、lock_alive 一类不单记，或只在 ⑤j2 的函数里面被调；到 ⑤j2 一起比；pause_requested、supervise_tick 归 ⑤j2 |
| `test_owner_takeover_closes_the_task` | 3230 | COVERED | hub-commands：cmd_task_close 5 次 |
| `test_finished_tasks_remove_their_stage_worktrees` | 3276 | COVERED | hub-commands：cmd_task_cleanup 4 次 |
| `test_task_brief_must_not_reference_uncommitted_paths` | 3373 | COVERED | hub-commands：cmd_task_new 4 次 |
| `test_metrics_reports_per_turn_costs_and_converts_legacy_session_totals` | 3737 | COVERED | hub-commands：cmd_metrics 1 次、exec_metrics 1 次、turn_metrics 1 次 |
| `test_owner_reply_piped_on_a_non_utf8_console_keeps_its_text` | 3883 | PARTIAL | hub-commands：cmd_send 1 次；命令拿到的文字已比；字节怎么解码归 ⑤j3（经真启动器用管道送字节） |
| `test_supervisor_runs_one_runner_per_task_up_to_the_limit` | 4050 | PARTIAL | hub-commands：configured_parallel 7 次；cmd_run、code_fingerprint、kernel_files、owner_sweep_tick、pause_requested、refuse_dirty_kernel、supervise、supervise_tick 归 ⑤j2 |
| `test_parallel_comes_from_the_flag_or_runner_json` | 4094 | COVERED | hub-commands：configured_parallel 4 次 |
| `test_serial_runner_refuses_while_task_runners_are_alive` | 4106 | PARTIAL | hub-commands：configured_parallel 1 次；cmd_run、refuse_dirty_kernel 归 ⑤j2 |
| `test_task_runner_exits_for_the_supervisor_on_kernel_changes` | 4118 | PARTIAL | 这条走到的 ⑤j1 函数（find_repo、lock_alive）没有单独记下的调用：task_quiet、lock_alive 一类不单记，或只在 ⑤j2 的函数里面被调；到 ⑤j2 一起比；cmd_run、kernel_settled、refuse_dirty_kernel 归 ⑤j2 |
| `test_exclusive_runs_the_command_once_executors_are_done` | 4427 | PARTIAL | 这条走到的 ⑤j1 函数（find_repo）没有单独记下的调用：task_quiet、lock_alive 一类不单记，或只在 ⑤j2 的函数里面被调；到 ⑤j2 一起比；cmd_exclusive 归 ⑤j2 |
| `test_exclusive_marks_an_owner_sweep_only_when_head_moves` | 4448 | PARTIAL | 这条走到的 ⑤j1 函数（find_repo）没有单独记下的调用：task_quiet、lock_alive 一类不单记，或只在 ⑤j2 的函数里面被调；到 ⑤j2 一起比；cmd_exclusive 归 ⑤j2 |
| `test_landing_waits_for_a_background_gate_sweep` | 4519 | PARTIAL | 这条走到的 ⑤j1 函数（find_repo）没有单独记下的调用：task_quiet、lock_alive 一类不单记，或只在 ⑤j2 的函数里面被调；到 ⑤j2 一起比；cmd_exclusive 归 ⑤j2 |
| `test_supervisor_starts_one_owner_sweep_at_a_time` | 4578 | PARTIAL | 这条走到的 ⑤j1 函数（lock_alive）没有单独记下的调用：task_quiet、lock_alive 一类不单记，或只在 ⑤j2 的函数里面被调；到 ⑤j2 一起比；owner_sweep_tick 归 ⑤j2 |
| `test_supervisor_counts_runners_left_by_its_previous_generation` | 4652 | PARTIAL | hub-commands：configured_parallel 7 次；cmd_run、code_fingerprint、kernel_files、owner_sweep_tick、pause_requested、refuse_dirty_kernel、supervise、supervise_tick 归 ⑤j2 |
| `test_supervisor_waits_for_a_settled_kernel_before_starting_runners` | 4671 | PARTIAL | hub-commands：configured_parallel 6 次；cmd_run、code_fingerprint、kernel_files、owner_sweep_tick、pause_requested、refuse_dirty_kernel、supervise、supervise_tick 归 ⑤j2 |
| `test_supervisor_ticks_the_owner_sweep_every_round` | 4679 | PARTIAL | hub-commands：configured_parallel 4 次；cmd_run、code_fingerprint、kernel_files、pause_requested、refuse_dirty_kernel、supervise、supervise_tick 归 ⑤j2 |
| `test_status_shows_the_parallel_runners` | 4689 | COVERED | cmd_status 1 次不重放；status 那次调用当时有活的持有者（.runners/T002），由 hub-commands-scenes 的 status 场景覆盖（真子进程拿着锁） |
| `test_supervisor_stays_while_a_runner_works_without_unread_letters` | 4727 | PARTIAL | hub-commands：configured_parallel 6 次；cmd_run、code_fingerprint、kernel_files、owner_sweep_tick、refuse_dirty_kernel、supervise、supervise_tick 归 ⑤j2 |
| `test_supervisor_stays_while_letters_are_held` | 4767 | PARTIAL | hub-commands：configured_parallel 5 次；cmd_run、code_fingerprint、kernel_files、owner_sweep_tick、pause_requested、refuse_dirty_kernel、supervise、supervise_tick 归 ⑤j2 |
| `test_serial_hub_stays_while_letters_are_held` | 4776 | PARTIAL | hub-commands：configured_parallel 1 次；cmd_run、code_fingerprint、kernel_files、refuse_dirty_kernel 归 ⑤j2 |
| `test_serial_hub_requeues_interrupted_stages_when_it_starts` | 4783 | PARTIAL | hub-commands：configured_parallel 1 次；cmd_run、code_fingerprint、kernel_files、refuse_dirty_kernel 归 ⑤j2 |
| `test_task_new_records_only_unfinished_dependencies` | 4833 | COVERED | hub-commands：cmd_task_new 3 次 |
| `test_passing_and_owner_close_release_the_dependents` | 4855 | COVERED | hub-commands：cmd_task_close 1 次 |
| `test_owner_commands_only_need_the_task_lock_under_a_supervisor` | 4882 | COVERED | task_quiet 由 hub-commands-scenes 的两条覆盖：supervisor 拿着总锁时只等主任务的锁；.runner 有人拿着、不是 supervisor 时照样要拿总锁 |
| `test_owner_rebases_a_task_before_its_contract_starts` | 4903 | COVERED | hub-commands：cmd_task_rebase 7 次 |
| `test_owner_adds_a_dependency_found_in_planning` | 4938 | COVERED | hub-commands：cmd_task_after 10 次 |
| `test_supervisor_picks_up_runner_json_changes_while_running` | 5002 | PARTIAL | hub-commands：configured_parallel 6 次；cmd_run、code_fingerprint、kernel_files、owner_sweep_tick、pause_requested、refuse_dirty_kernel、supervise、supervise_tick 归 ⑤j2 |
| `test_supervisor_restart_keeps_where_parallel_came_from` | 5035 | PARTIAL | hub-commands：configured_parallel 6 次；cmd_run、refuse_dirty_kernel、supervise 归 ⑤j2 |
| `test_supervisor_keeps_going_after_a_bad_tick` | 5067 | PARTIAL | hub-commands：configured_parallel 5 次；cmd_run、code_fingerprint、kernel_files、owner_sweep_tick、pause_requested、refuse_dirty_kernel、supervise、supervise_tick 归 ⑤j2 |
| `test_supervisor_stops_restarting_a_crashing_runner` | 5086 | PARTIAL | hub-commands：configured_parallel 7 次；cmd_run、code_fingerprint、kernel_files、owner_sweep_tick、pause_requested、refuse_dirty_kernel、supervise、supervise_tick 归 ⑤j2 |
| `test_owner_unsticks_a_stage_nobody_is_working_on` | 5425 | COVERED | hub-commands：cmd_task_unstick 8 次 |
| `test_facts_checked_before_the_plan_is_delivered_says_why` | 5777 | COVERED | hub-commands：cmd_send 1 次 |
| `test_owner_raises_the_attempt_budget` | 6223 | COVERED | hub-commands：cmd_task_budget 10 次 |
| `test_owner_commands_pause_a_busy_task_runner` | 6346 | PARTIAL | 这条走到的 ⑤j1 函数（find_repo、lock_alive、pause_marker、supervisor_alive、task_quiet）没有单独记下的调用：task_quiet、lock_alive 一类不单记，或只在 ⑤j2 的函数里面被调；到 ⑤j2 一起比；cmd_run、pause_requested、refuse_dirty_kernel、supervise_tick 归 ⑤j2 |
| `test_answers_to_questions_before_the_contract_are_recorded_as_decisions` | 6449 | COVERED | hub-commands：cmd_send 8 次 |
| `test_an_owner_reply_releases_the_gate_claim_and_long_letters_are_refused` | 6579 | COVERED | hub-commands：cmd_send 2 次 |
| `test_owner_rework_records_the_letter_text` | 6743 | COVERED | hub-commands：cmd_send 1 次 |
| `test_ledger_session_and_decision_records_with_u2028_are_read_back` | 6907 | COVERED | hub-commands：exec_metrics 1 次 |
| `test_the_hub_refuses_to_start_on_a_changed_kernel` | 7905 | PARTIAL | 这条走到的 ⑤j1 函数（find_repo）没有单独记下的调用：task_quiet、lock_alive 一类不单记，或只在 ⑤j2 的函数里面被调；到 ⑤j2 一起比；cmd_run、refuse_dirty_kernel 归 ⑤j2 |

COVERED 20、PARTIAL 25。PARTIAL 里 24 条剩 ⑤j2（cmd_run、supervise 一类，逐条写在上表），3883 剩 ⑤j3：它在 j1 只比到“命令拿到的文字”，字节怎么解码要经真启动器比（themistally-04 定的）。设计稿第 1 节估的是 19 条转 COVERED，多出的 4689 是 configured_parallel 中段挪进 j1 之后它走到的函数都在 j1 了。

变异：ts/mutations/hub-j1.ts.json 共 93 条（commands.ts），全部抓住，没有判等价的，没有靠超时的。前 88 条分三段跑，后 5 条补 themistally-04 的抽查：
- 第一段只跑手写场景（当时的 5 条 it），抓住 13 条。
- 第二段：漏掉的 75 条，用存下的 145 次样本请求让 node 重放，抓住 54 条，漏 21 条。
- 漏掉的 21 条都是样本走不到的分支，补了 8 条 it：
  - task new：不合格的主任务号与 slug、重复登记（J13、J14、J16），--no-jev（J20），任务书里不带斜杠的路径（J23）与几处没提交的路径的次序（J26）；
  - task close 的收尾没做完要打印（J32），task after 的依赖排序（J41）；
  - task budget：墙钟取较大值（J52）、Budget 行不唯一（J54）、执行端在办（J56）、主任务停了（J58）；
  - send：blocked 的恢复（J67）、停止（J73）、正文 36 行（J71）；exec-recheck 没过的退出码（J74）；
  - 锁：pid 问不出死活（J02）、runner 目录的排序（J77）、parallel 是负数（J06）、.runner 有人拿着却不是 supervisor（J03）、暂停标记里的 pid（J11，盯梢进程看别的进程问得到它活着）。
  - J06 第一次写的 parallel 是 0，漏了：Python 的 value or 1 先把 0 变成 1，走不到 max(1, …)；改成 -2 后抓住。
- 第三段：这 21 条按“该由哪条 it 抓住”分 8 组，每组用 vitest -t 只跑那一条 it（每组的基准都是 1 passed、12 skipped），全部抓住。20 条是三边对照比出的不同，J11 是盯梢进程的断言不符。
- 抽查：themistally-04 在 1f87edd 上另写 15 条（commands.ts），抓住 10 条。漏的 5 条它都对过 Python，都是真缺口；各补一个三边场景，照原样加进清单（J89–J93），按 it 分 3 组用 vitest -t 跑（每组的基准都是 1 passed、15 skipped），全部抓住：
  - J89（抽查 S05）：没登记的主任务带 --decision 回复，先报没有登记、信不投；
  - J90（抽查 S08）：status 读 .runner 的 owner.json 要去空白，DirLock 写的带结尾换行（kit_hub.py:898–899）；
  - J91（抽查 S09）：回合记录没有 session_key 时主任务写“?”，--json 与表格两份都比；
  - J92（抽查 S10）：收到 exec.finished 之后撤掉 started，同一个 run_dir 的第二条不再算一次；
  - J93（抽查 S11）：锁目录里还没有 owner.json、或是空文件时不去问死活，算活着（DirLock 先建目录、再写文件，kit_hub.py:897–899）。
- readStdin 的变异（去掉 ignoreBOM、不换通用换行）放进 ⑤j3：j1 的契约换成记下的文字，走不到它。

其余场景随各片补（⑤j2、⑤j3）。

### ⑤j2 进程模型

做法（⑤j 设计稿第 4–7 节，themistally-04 复核设计、中段与移植）：
- 新模块 @themis/hub/runner：kit_hub.py 的 kernel_files、code_fingerprint、kernel_dirty、kernel_changes、refuse_dirty_kernel、kernel_settled、spawn_runner、pause_requested、cmd_run、spawn_task_runner、owner_sweep_tick、cmd_owner_sweep、supervise_tick、supervise、cmd_exclusive。
- E3：kernel_files 看选择文件。hub 是 ts 时，多出五个包（base、config、dispatcher、hub、cli）src 下的全部文件与依赖清单（package.json、bun.lock、bunfig.toml、各包的 package.json、tsconfig.json），按码点排。选择文件坏了当没写（kernel_selection 交回空）。实测 145 个文件，10.2 毫秒。
- 起长命子进程（spawn_runner、spawn_task_runner、owner_sweep_tick 起的 owner-sweep）：Windows 上不经 child_process。
  - 原因：libuv 把不带 detached 的子进程放进它自己的 Job（KILL_ON_JOB_CLOSE），父进程一退子进程就被杀；带 detached 又多了 DETACHED_PROCESS 与 CREATE_NEW_PROCESS_GROUP。
  - 改成 base/native.ts 的 CreateProcessW（bun:ffi），同 Python 的 Popen：flags 0；属性表只放三个标准句柄；stdin 接 NUL；有日志时 stdout、stderr 都接日志，没有时继承本进程的标准句柄。
  - 所以 hub 在 Windows 上只跑在 Bun 下，没有标准句柄时接 NUL（计划第 10 节两行）。POSIX 用 child_process.spawn 加 unref。
  - native.ts 把 CreateProcessW 抽成共用的 create，spawnSuspended 也走它；另加 inheritableStd（DuplicateHandle 出可继承的一份）。
- 跑到静止换成真的 cmd_run。
  - 探针请求带 clock "sleep"：sleep 把钉住的时钟往后挪，monotonic、time 跟着钉住的时钟；内核指纹固定，kernel_changes 交回空；第 400 次 sleep 报错。
  - ⑤i2 两边探针里照 cmd_run 抄的驱动删掉，计划第 10 节那一行关掉。
- 采样器给 9 个函数装流程记录器。
  - cmd_run、cmd_owner_sweep、cmd_exclusive 同站主命令记（Namespace、stdout、stderr）；supervise_tick、owner_sweep_tick、spawn_runner、spawn_task_runner、refuse_dirty_kernel、pause_requested 的第一个参数是 hub。
  - 内层换掉的有：spawn_task_runner、spawn_runner、kernel_dirty、kernel_settled、code_fingerprint、kernel_changes、tasks_with_work、requeue_interrupted、owner_sweep_tick、Popen、sleep、Engine.step。
  - 进程记成编号与 pid，重放时换成假进程。
  - 账本里进程自己的 pid 换成占位再比（themistally-04 定的）。runner.child_started 的 pid 是注入的子进程号，照原样比。
- 用例清单由 scratchpad 的 j2_tests.py 从 i_trace2.json 机械得出：31 条。⑤j1 一节写着“归 ⑤j2”的 24 条 PARTIAL 都在里面（脚本核过）。

契约：
- hub-runner：31 条用例，最外层调用 69 次：cmd_run 20、code_fingerprint 10、kernel_files 7、cmd_exclusive 7、owner_sweep_tick 6、supervise_tick 5、kernel_dirty 4、pause_requested 4、refuse_dirty_kernel 3、spawn_task_runner 2、spawn_runner 1。
  - 跳过 5 次：1097 的 spawn_runner 起真子进程；4106、4652、4727 的 cmd_run 与 4578 的 owner_sweep_tick，调用当时有活的持有者。都由手写场景覆盖。
  - 注入：kernel_dirty 29、proc.poll 26、kernel_changes 20、code_fingerprint 20、spawn_task_runner 19、tasks_with_work 8、pid_alive 7、Engine.step 6、_running_attempts 6、Popen 4、spawn_runner 3、release_held 3、sleep 3、owner_sweep_tick 2、kernel_settled 2、requeue_interrupted 1。
  - 流程函数 43 次、只读的 21 次，三边重放都与当时的结果相同（交回值、文件、账本、git 状态、stdout、stderr）。
- hub-runner-scenes：21 条 it。
  - 采样跳过的 5 条：
    - spawn_runner 真起子进程：三边交回时子进程还在跑；bun 上起它的进程退出之后，子进程照样跑完；
    - 另一个进程（真的 Python 子进程）拿着锁时的 cmd_run、owner_sweep_tick、supervise_tick。
  - 采样没调到的 3 条：owner-sweep 的两种退出；exclusive 交回命令的退出码、命令起不来报 FileNotFoundError；选择文件（只测 TS）。
  - 起长命子进程 2 条，Python 的 Popen 与 bun 的 CreateProcessW 逐字比：
    - 日志追加、stderr 并进 stdout、工作目录、stdin 是空设备、退出码、不给日志、起不来的报错；
    - 子进程读自己 PEB 里的 ConsoleFlags 是 0，即没另起进程组（themistally-04 提的办法，不发任何信号）；
    - Node 下报“只跑在 Bun 下”；
    - 本进程另开的可继承句柄子进程拿不到（N01，见下）。
  - 真的 git status 1 条（7873、7893）；E3 的内核文件 1 条。
  - 变异补的 5 条，补 themistally-04 抽查的 4 条（另有两处并进了已有的 it），见下面的变异一段；每条 it 的标题写了对着哪几条变异或哪几条抽查。
- hub-quiesce：种子 1–30，三边用真的 cmd_run 从同一个初始信箱照同一份剧本跑到静止，逐字相同。
- base 的 supervise 单测：假 API 加了 spawn、inheritableStd（调用就抛），37 条都过。

| 用例 | 行 | 状态 | TS 契约 |
|---|---|---|---|
| `test_runner_exits_between_steps_once_the_kernel_changes` | 1027 | COVERED | hub-runner：code_fingerprint 7 次、kernel_files 6 次、cmd_run 1 次；⑤j1 的部分见上一节 |
| `test_runner_restarts_on_committed_kernel_changes` | 1082 | COVERED | hub-runner：cmd_run 2 次；⑤j1 的部分见上一节 |
| `test_spawn_runner_returns_while_the_new_hub_runs` | 1097 | COVERED | spawn_runner 1 次不重放；hub-runner-scenes 的 spawn_runner 两条覆盖：三边交回时子进程还在跑；bun 上起子进程的进程退出之后子进程照样跑完 |
| `test_kernel_dirty_reads_git_status` | 1124 | COVERED | hub-runner：kernel_dirty 4 次 |
| `test_supervisor_puts_due_letters_back_and_starts_their_runner` | 1925 | COVERED | hub-runner：supervise_tick 1 次；⑤j1 的部分见上一节 |
| `test_supervisor_requeues_only_tasks_nobody_is_working_on` | 2057 | COVERED | hub-runner：supervise_tick 2 次；⑤j1 的部分见上一节 |
| `test_supervisor_runs_one_runner_per_task_up_to_the_limit` | 4050 | COVERED | hub-runner：cmd_run 1 次；⑤j1 的部分见上一节 |
| `test_serial_runner_refuses_while_task_runners_are_alive` | 4106 | COVERED | cmd_run 1 次不重放；hub-runner-scenes 的 cmd_run 场景覆盖（真子进程拿着 .runners/T002）；⑤j1 的部分见上一节 |
| `test_task_runner_exits_for_the_supervisor_on_kernel_changes` | 4118 | COVERED | hub-runner：cmd_run 1 次；⑤j1 的部分见上一节 |
| `test_exclusive_runs_the_command_once_executors_are_done` | 4427 | COVERED | hub-runner：cmd_exclusive 3 次；⑤j1 的部分见上一节 |
| `test_exclusive_marks_an_owner_sweep_only_when_head_moves` | 4448 | COVERED | hub-runner：cmd_exclusive 3 次；⑤j1 的部分见上一节 |
| `test_landing_waits_for_a_background_gate_sweep` | 4519 | COVERED | hub-runner：cmd_exclusive 1 次；⑤j1 的部分见上一节 |
| `test_supervisor_starts_one_owner_sweep_at_a_time` | 4578 | COVERED | hub-runner：owner_sweep_tick 5 次；owner_sweep_tick 1 次不重放；hub-runner-scenes 的 owner_sweep_tick 场景覆盖（真子进程拿着 .owner-sweep）；⑤j1 的部分见上一节 |
| `test_supervisor_counts_runners_left_by_its_previous_generation` | 4652 | COVERED | cmd_run 1 次不重放；hub-runner-scenes 的 supervise_tick 场景覆盖（真子进程拿着 .runners/T001，占一个名额）；⑤j1 的部分见上一节 |
| `test_supervisor_waits_for_a_settled_kernel_before_starting_runners` | 4671 | COVERED | hub-runner：cmd_run 1 次；⑤j1 的部分见上一节 |
| `test_supervisor_ticks_the_owner_sweep_every_round` | 4679 | COVERED | hub-runner：cmd_run 1 次；⑤j1 的部分见上一节 |
| `test_supervisor_stays_while_a_runner_works_without_unread_letters` | 4727 | COVERED | cmd_run 1 次不重放；hub-runner-scenes 的 supervise_tick 场景覆盖（没有待办时上一代的 runner 在跑也算忙）；⑤j1 的部分见上一节 |
| `test_supervisor_stays_while_letters_are_held` | 4767 | COVERED | hub-runner：cmd_run 1 次；⑤j1 的部分见上一节 |
| `test_serial_hub_stays_while_letters_are_held` | 4776 | COVERED | hub-runner：cmd_run 1 次；⑤j1 的部分见上一节 |
| `test_serial_hub_requeues_interrupted_stages_when_it_starts` | 4783 | COVERED | hub-runner：cmd_run 1 次；⑤j1 的部分见上一节 |
| `test_supervisor_picks_up_runner_json_changes_while_running` | 5002 | COVERED | hub-runner：cmd_run 1 次；⑤j1 的部分见上一节 |
| `test_supervisor_restart_keeps_where_parallel_came_from` | 5035 | COVERED | hub-runner：cmd_run 2 次；⑤j1 的部分见上一节 |
| `test_fingerprint_survives_a_file_being_swapped` | 5055 | COVERED | hub-runner：code_fingerprint 3 次 |
| `test_supervisor_keeps_going_after_a_bad_tick` | 5067 | COVERED | hub-runner：cmd_run 1 次；⑤j1 的部分见上一节 |
| `test_supervisor_stops_restarting_a_crashing_runner` | 5086 | COVERED | hub-runner：cmd_run 1 次；⑤j1 的部分见上一节 |
| `test_pi_workers_load_the_guard_with_the_kernel_roots` | 5946 | COVERED | hub-runner：kernel_files 1 次 |
| `test_owner_commands_pause_a_busy_task_runner` | 6346 | COVERED | hub-runner：pause_requested 4 次、supervise_tick 2 次、cmd_run 1 次；⑤j1 的部分见上一节 |
| `test_kernel_changes_lists_uncommitted_kernel_files` | 7873 | COVERED | 用例经 REAL_KERNEL_CHANGES 调，采样器包不到；hub-runner-scenes 的真 git status 场景覆盖 |
| `test_kernel_changes_counts_a_git_error_as_changed` | 7893 | COVERED | 用例经 REAL_KERNEL_CHANGES 调，采样器包不到；hub-runner-scenes 的真 git status 场景覆盖（GIT_DIR 指向不在的目录） |
| `test_the_hub_refuses_to_start_on_a_changed_kernel` | 7905 | COVERED | hub-runner：refuse_dirty_kernel 3 次、cmd_run 1 次；⑤j1 的部分见上一节 |
| `test_the_supervisor_passes_the_override_on_to_task_runners` | 7927 | COVERED | hub-runner：spawn_task_runner 2 次 |

COVERED 31。⑤j1 一节里剩 ⑤j2 的 24 条在这一片都比到了；3883 仍剩 ⑤j3。

变异：ts/mutations/hub-j2.ts.json 共 115 条：
- runner.ts 的 R01–R96（去掉 R82），与补抽查的 R97–R103；
- 探针与 popen 的 P01–P09；
- native.ts 的 N01–N04。

抓住 114 条，R83 判等价，没有靠超时的。前 108 条分四段跑，后 7 条补 themistally-04 的抽查：
- 第一段只跑 hub-runner-scenes（当时还没有变异补的那 5 条 it），抓住 46 条，漏 63 条。P04（popen 另起进程组）在加了 ConsoleFlags 那一段之后单独重跑，抓住了。
- 第二段：漏掉的 62 条，用存下的 64 次样本请求让 node 重放，抓住 46 条，漏 16 条。
- 第三段：前 15 条只跑 hub-quiesce，抓住 R44（落成不算一件事，“处理了 N 件事”对不上）；N01 只跑 supervise 契约，没抓住。
- 补了 6 条 it（变异补的 5 条，加 popen 那组的 N01），第四段按“该由哪条 it 抓住”分 6 组，每组用 vitest -t 只跑那一条 it。每组的基准都是 1 passed、16 skipped。14 条全部抓住（R44 也放进去，结项信那条 it 也抓得住）：
  - R39–R44，结项信：
    - 被别的主任务的执行端挡两轮：finalize.deferred 只记一次，提示只打一次，每轮各睡 poll 秒（R41、R42、R43）；
    - 落成（finalize 照剧本交回没过）算一件事（R44）；
    - “返工”类型的 exec-step 信不当结项信（R39）；
    - run --task T001 不办 T002 的结项信（R40）。
  - R25、R47，等待：
    - idle_exit 没到不退。前提是同一个信箱 idle_exit 为 0 时空闲就退（runner_may_idle_exit 是真），这一条先验过（themistally-04 要的）；
    - 内核变了等落定时，poll 0.05 也至少睡 0.1 秒。
  - R78、R70，supervise：
    - .runner/mode 只在拿着总锁时在（DirLock 退出时整个目录删掉），所以在第一轮末尾的 sleep 里当场读它；
    - supervise_tick 放回时跳过挂着活暂停标记的主任务，inner 核对 requeue_interrupted 的 skip。
  - R30、R55：
    - pause_requested 问不出命令进程的死活（None）时当它还在（kit_hub.py 用的是 is False）；
    - spawn_task_runner 的 args 是 None 时，先建好日志再报 AttributeError。采样里 supervise_tick 有 5 次传 None，只是那几次 spawn_task_runner 被换掉了，所以分支留着。
  - R91，exclusive：被挡两轮，“等这些跑完”只说一次，sleep 是 5、5。
  - N01，只继承三个标准句柄（themistally-04 提的办法）：
    - 起之前，本进程另开一个可继承句柄，命令行里给出它的数值；
    - 子进程用 GetFinalPathNameByHandleW 问这个数值对应的路径，以那个独有的文件名结尾才算继承到了，数值碰巧撞上子进程自己的句柄也不会误判；
    - 两边探针的 hub.popen 都加了 inherit，Python 走 close_fds 的 HANDLE_LIST，逐字比；
    - 变异体不加 EXTENDED_STARTUPINFO_PRESENT，CreateProcessW 不认属性表，子进程打印 inherited。
- 删掉的 1 条：R82（LandBusy 记成 HubError）。
  - themistally-04 指出 LandBusy 只在 exec_window 里抛，进不了 supervise_tick、owner_sweep_tick，supervisor.error 拿不到它。
  - supervisor.error 的类名改用 engine.ts 的 pyErrorNames（改成 export），runner.ts 不再另抄一份。两边逐种核过：LandBusy、HubError、DispatchError、pyExceptionName、error.name，最后兜底 Exception。
  - 这条规则由 ⑤i 的变异覆盖；R81 的原文跟着换。
- 判等价的 1 条：R83（换代的 --parallel 用起步时的值）。
  - 只在 args.parallel 不是 None 时加这个参数。这时 configured_parallel（kit_hub.py:6242）每轮都交回 max(1, int(args.parallel))，与 cmd_run 传进来的初值相同。
  - 只有直接拿别的 parallel 调 supervise 才分得出，生产上没有这样调的（themistally-04 定的）。
- 跟着修的旧清单：native.ts 抽出共用的 create 之后，lasterror-e 的 E4 与 supervise 的 V16、V17、N01 原文对不上，mutation-specs 报“出现 0 次”。
  - 照现在的代码改了原文与改法，意思不变。
  - 四条按各自清单的命令重跑：都抓住了（lasterror-e 1 条、supervise 3 条，两份基准都 passed）。
  - hub-j2 生成时、另两份这次改写时都用了 Path.write_text，Windows 上写成了 CRLF，三份都已换回 LF（HEAD 里的清单都是 LF）。
- 抽查：themistally-04 在 b88f346 上另写 15 条（runner.ts 14 条、native.ts 1 条），基准 45 passed，抓住 6 条，漏 9 条：
  - 判等价的 2 条：
    - T03：kernel_settled 的时限 >= 改成 >；
    - T11：supervise 空闲到点 >= 改成 >。
    - 理由：生产与场景里 monotonic 是高精度的真时钟，正好相等几乎不可能；只有跑到静止的时钟是钉住的，而那里走不到这两处（themistally-04 定的）。
  - 真缺口 7 条。各补了场景，照原样加进清单（R97–R103），用 vitest -t 只跑标题带“抽查 T”的 6 条 it（基准 6 passed、15 skipped），全部抓住：
    - R97、R98（抽查 T01、T02）：refuse_dirty_kernel 拒绝时，账本只记前 20 条改动、报错只列前 10 条；放行时也只记前 20 条（kit_hub.py:440–444）。
    - R99（抽查 T04）：空的暂停标记照 read_text(marker) or "{}" 当 {} 处理，交回 True、标记留着（6193）。read_text 遇到 OSError 也交回 ""，不只手改过的标记才是空的。
    - R100（抽查 T06）：exec-step 里同时有两封结项信时，照名字的次序先办第一封（6298）。themistally-04 拿 hub-quiesce 重跑过，也抓不住，这条场景是必需的。
    - R101（抽查 T09）：supervise_tick 算上一代的 runner 时，不算自己 children 里的（6433，Python 短路，不对它们调 lock_alive）。在跑的子进程都拿着自己的 .runners/<task>，生产上每一轮都会走到。
    - R102（抽查 T13）：exclusive.run 只记命令的前 6 项（6617）。R91 那条 it 的命令改成 7 项。
    - R103（抽查 T14）：cmd_owner_sweep 只把退出码是 EXIT_BLOCKED 的 HubError 当成“已经有一个在跑”（6404）。场景让还没有提交的仓库在 owner_sweep_run 里 git rev-parse HEAD 失败；HubError 的缺省退出码是 EXIT_FAIL（469），三边都照抛。

### ⑤j3 转交

第一个提交是覆盖审计，转交本身另起提交，接在本节后面。

覆盖审计（⑤j3 设计稿第 5 节，themistally-04 定的做法）：
- 起因：写 ⑤j3 设计稿时机械核对整份文档（scratchpad 的 j3_open_rows.py、j3_missing_rows.py）。
  - tests/test_kit_hub.py 共 299 条，表里有行的 289 条；
  - 3403、3408、3509、3516、3529、3872、4705、4796、7055、7318 这 10 条一次也没出现，连 MISSING 都没记；
  - 5227 停在 ⑤a 一节的 PARTIAL（写“归 ⑤d”），⑤d 一节没有再列它。
- 做法：逐条照 i_trace2.json 记的走到的函数，与各片采样的用例清单核。
  - 样本里有这条用例的调用，就补行写 COVERED；
  - 没有就补场景；
  - 走到的分支已有三边对照的手写场景，按分支等价写 COVERED，写明是哪条场景、哪种假 pi 模式。
- 这 10 条都不在任何一片的采样清单里，补了 4 条场景（3529、4705、4796、7055）。
- 4705 要比 sleep 的秒数：gatepost.ts 的 addWorktree 把重试之间的等待抽成可注入的 sleep。
  - GatePostDeps 多一项可选的 sleep，没给用真的；
  - 探针在剧本里有 sleep 时换上，Python 那边换的是 kit_hub.time.sleep。
  - hub-f 清单的 P12（重试之前不等）原文跟着换到缺省 sleep 里的 setTimeout，照 hub-f 的命令重跑，抓住。

| 用例 | 行 | 状态 | TS 契约 |
|---|---|---|---|
| `test_coordinator_runs_at_high_effort` | 3403 | COVERED | hub-state.compare「常量与 kit_hub 的同名常量逐项相同」：用例只断言 ROSTER 的取值，常量那条逐项比 |
| `test_only_the_planner_stays_on_claude` | 3408 | COVERED | 同上：ROSTER 各岗位的 adapter、provider、model、effort、thinking，与 CONTRACT_EXECUTOR_LINE |
| `test_the_pi_worker_command_carries_every_resource_flag` | 3509 | COVERED | 分支等价：hub-turn「pi：交差成功……被拦（参数不认、--help 读不出）」，起 pi 工人的命令行三边逐字比（假 pi 的 ok 模式），资源参数都在命令里 |
| `test_a_pi_worker_is_not_started_when_pi_does_not_know_a_flag` | 3516 | COVERED | 分支等价：同一条场景，假 pi 的 missing 模式（--help 少一个参数，不起这一回合）与 fail 模式（--help 读不出） |
| `test_pi_help_is_probed_once_per_pi_command` | 3529 | COVERED | hub-audit「探 --help 时带着资源参数……（3529，⑤j3 覆盖审计补）」：三边各跑一批，比交回值与每边起假 pi 的次数；并发调用只探一次另由 ⑤e0 那条只测 TS 的场景钉住 |
| `test_cli_output_survives_a_non_utf8_console` | 3872 | COVERED | 只走 Python 留下的部分：--help 由 Python 的 argparse 回答、不转交（⑤j3 设计稿第 1 节），第 ⑥ 步撤 argparse 时再比 |
| `test_worktree_add_retries_when_git_metadata_is_busy` | 4705 | COVERED | hub-gatepost-scenes「ensure_worktree：git worktree add 失败就重试……（4705，⑤j3 覆盖审计补）」：不存在的提交让三次都失败，sleep 照剧本换，记下的秒数 [1, 2] 与报错三边比 |
| `test_dependent_task_plans_first_and_waits_for_its_dependencies` | 4796 | COVERED | hub-state.compare「守卫：开工、返工、通过……（按步骤）」照用例补的一段：带两个依赖时规划照常开工，合同端被挡、下一步里也不列它，after_released 之后放行 |
| `test_audit_may_return_several_stages_and_the_upstream_one_goes_first` | 5227 | COVERED | ⑤a 一节记 PARTIAL 的最后两句：ROLE_EXTRA_OUTPUT 由 hub-state.compare 的常量一条逐项比；worker.md 是两边共用的同一份模板文件（TEMPLATE_DIR），hub-prompt 照它渲染、三边比 |
| `test_background_sweeps_queue_behind_each_other` | 7055 | COVERED | hub-sweep-scenes「后台回归之间排队……（7055，⑤j3 覆盖审计补）」：另一个进程拿着 .sweep 时，owner_sweep 等 sweep_wait（同用例，把 SWEEP_WAIT_SECONDS 改短）超时原样抛出，没挂标记、没碰 .land；锁拿过又放掉之后照常拿到、跑完 |
| `test_deeply_nested_tool_args_are_read_without_recursion` | 7318 | COVERED | hub-audit「工具参数嵌套到 960、997 层（第 134 轮）」。用例里 2000 层那一种落在计划第 10 节“hub 审计遇到嵌套很深的值”那条已接受的不同里：TS 的 loads 在 1000 层封顶；Python 3.12.10 实测直接调用到 2997 层，隔 60 层 C 调用是 2877 层 |

全表合计（机械核对，每条用例取最后一行的状态）：tests/test_kit_hub.py 共 299 条，都有行；COVERED 298、PARTIAL 1。不是 COVERED 的：test_owner_reply_piped_on_a_non_utf8_console_keeps_its_text（3883 留给转交那一提交，经真启动器用管道送字节）。

变异：ts/mutations/hub-j3a.ts.json 共 9 条，用 vitest -t 只跑四个契约文件里标题带“覆盖审计补”或“按步骤”的 5 条 it（基准 5 passed、64 skipped），全部抓住：
- A01、A02（3529）：探 --help 不带资源参数；不缓存。
- A03–A05（4705）：worktree add 不重试；重试之间不睡；睡的秒数翻倍。
- A06–A08（4796）：守卫不看依赖；依赖放行了也挡；规划也被依赖挡。
- A09（7055）：标记挂在拿 .sweep 之前。
