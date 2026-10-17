# 10 S4 status/brief 阶段复审

状态：`ACCEPTED_WITH_EXCEPTION`

## 已复核出口

- `ViewPackageStore` 将 state、brief、manifest 写入不可变 view 目录，并在写锁内用 `current.json` 做最后的原子替换；`expected_view_id` 不匹配时拒绝 CAS。
- `read_current` 校验 pointer、manifest、state/brief 原始字节摘要，删除/篡改/半写包不会被当作当前视图。
- `render_project_brief` 使用固定排序和 UTF-8 字节上限，无法容纳时明确拒绝，不静默截断必需内容。
- `make_read_receipt` 绑定 view、manifest、观察者和游标，重复同一输入得到同一 receipt；读取不会改变业务状态。

## 证据

```text
python -B -m unittest tests.test_project_events tests.test_project_journal tests.test_project_sources tests.test_project_state tests.test_project_recovery tests.test_project_views -q
Ran 23 tests in 0.243s
OK (skipped=1)
python -m compileall -q scripts/codekit tests                         PASS
seven 10 schemas                                                       JSON parse PASS
git diff --check                                                        PASS
```

宿主不支持符号链接的 fixture 仍会跳过；真实并发崩溃、断电和跨平台替换权限仍 `NOT_RUN/BLOCKED`。

## 未覆盖与边界

- S4 没有接入 09/07/03/05 权威数据、outbox/cursor、通知 adapter 或生产状态别名。
- current 指针只控制读取投影版本，不授予 dispatch、approval、budget 或 stop 权限。
