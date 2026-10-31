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
| `test_legacy_task_without_external_facts_is_not_blocked` | 1807 | COVERED | guard 一句在「守卫：热修补……」；external_facts_section 在 hub-prompt（⑤d1）的记下的调用 |
| `test_audit_may_return_several_stages_and_the_upstream_one_goes_first` | 5223 | PARTIAL | letter_errors、return_stages、guard、hotfix_reason 都在「守卫：热修补……」；最后两句核对提示词（ROLE_EXTRA_OUTPUT、worker.md）归 ⑤d |
| `test_owner_ordered_gate_rework_is_a_hotfix_and_holds_the_executor_back` | 5460 | COVERED | hub-state.compare「守卫：热修补……」 |
| `test_a_gate_claim_opens_the_hotfix_and_holds_the_executor_until_the_gate_redelivers` | 6604 | COVERED | 同上 |
| `test_the_schema_subset_validator（34 个参数）` | 7231 | COVERED | hub-state.compare「schema 子集」：hub.samples 取 SCHEMA_SAMPLES |
| `test_role_schemas_only_use_the_subset_and_match_the_kernel` | 7235 | COVERED | 同上：五份岗位 schema 加四种子集外写法 |
| `test_routine_letters_map_to_the_next_step（11 个参数）` | 7480 | COVERED | hub-state.compare「信件」：hub.samples 用用例的 routine_letter 渲染 |
| `test_exceptions_go_to_the_coordinator（7 个参数）` | 7495 | COVERED | 同上 |
| `test_routine_briefs_quote_each_path_on_its_own` | 7673 | COVERED | hub-state.compare「守卫：开工、返工、通过」：engine_env 只提供仓库与状态，直接调 |
| `test_downstream_notes_ride_along_to_every_later_turn` | 7729 | COVERED | upstream_notes 在随机对照里；进回合输入（turn_prompt）与 letter_from_output 在 hub-prompt（⑤d1）的记下的调用 |
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

其余场景随各片补（⑤e 到 ⑤j）。
