# 01 收尾口径裁决（acceptance.md 第 7 节第 20–23 项）

裁决人：规划端（Claude Code），2026-09-26。本文件单独存放，目的是不改动 `decisions.md`、`acceptance.md` 与基线报告中已经登记的摘要。本文件是这四项的最终口径，与 `decisions.md` 收尾轮裁决（R-01、R-02、R-P12）一起读。

| 项 | 问题 | 裁决 | 对判定的影响 |
|---|---|---|---|
| 20 | R-01 受控禁用的证据等级：`PYTHONPYCACHEPREFIX` 的设置与“取证前为空”只有操作者记录 | **接受**。依据是取证循环当场写出、已归档并登记摘要的操作者记录（`evidence/run-controls-closure/closure-captures.txt`，sha256 `fb00af74…0e86`），证据等级按 **source_reported** 记，不升级为取证工具实测。后续取证建议把 `PYTHONPYCACHEPREFIX` 加入 `scripts/codekit/baseline.py` 的 `ENV_NAME_ALLOWLIST`，并记录前缀目录在取证前后的条目数。这是改进项，不阻断本次判定 | 01-A01 维持“PASS（Windows）”，前提写明：pyc 受控禁用的依据是 source_reported 的操作者记录 |
| 21 | R-01 是否覆盖仓库外输入（标准库及其字节码、git 与全局配置、系统工具） | **不覆盖**。R-01 的对象是文档 2.2 的 `worktree_input_manifest`，即仓库工作区内被读取的字节。仓库外输入属于同一节中独立的 `environment_facts_ref`：记录版本与定位（`environment.json`），不计摘要，并作为 `closure_gaps` 如实声明（取证工具已声明 `out_of_repo_inputs_not_included`） | 01-A01 不因仓库外输入判 FAIL；“可严格复现”的声明仍不成立，报告已写明输入闭包为 partial |
| 22 | G5 在 R-02 下的读法：a4fa199 的 G5 恒为通过，没有可触发的失败路径 | **按不变式映射算满足**。旧实现的 G5 在构造上不做机械判定（`scripts/pi_dispatch.py:4153-4154`，质量复审由复审报告负责），所以不存在“可触发的失败断言”。R-02 要求的是回归映射；对没有失败路径的门，映射就是断言这个不变式：恒为通过并带固定备注，在其他门失败的记录中也一样（P4-G09、G23）。以后若有模块给 G5 加入机械判定，必须补失败路径断言，否则该模块的 A07 类验收不成立 | 01-A07 维持“PASS（Windows，范围限定）”，`unmet_within_scope` 不变 |
| 23 | legacy-inventory 9.10.6 (c) 类 23 行只有旧自测的 check，不符合 R-P12 的 `<类>.<方法>` 写法 | **扩展 R-P12 的内联写法**：模块级测试函数加 check 的形式记为 `inline:tests/test_dispatch.py::<函数名>#<check 名>@<测试文件 sha256>`。测试文件摘要取取证输入清单中的值；旧自测的 `tests/test_dispatch.py` 在 HEAD 与全部取证中字节相同。比较投影记为 `codekit01-characterization-v1`（该 check 的断言）。legacy-inventory 第 9 节已经列出这 23 行的函数名与 check 名，按上述写法即可直接得出引用，不再逐行改写该文件（避免牵动已登记的摘要）；下次修订清单时再展开 | 这 23 行在迁移比较中视为“有代码内联 fixture 与特征化断言”；新旧差分仍按 R-P12 的规则 |

仍然需要用户决定的事项不在本文范围内，见 `acceptance.md` 第 9 节：保护范围、提交范围、是否在 Linux/macOS 运行、是否安装 jsonschema、失效的索引链接。

## 提交前追加的局部决定（2026-09-26）

| 编号 | 决定 | 理由 |
|---|---|---|
| 01-L10 | `.gitattributes` 追加 `-text`：`scripts/codekit/*.py`、01 新增的 9 个测试与辅助文件、`scripts/pi_dispatch.py`、`tests/test_dispatch.py`、`tests/stub_pi.py`、`tests/stub_pi_help.txt`、`docs/themis-tally-v2/**`、`docs/themis-tally-v2-design.md` | 提交前检查发现：这些文件工作区为 LF，且没有 `-text`；本机系统级 `core.autocrlf=true` 会在今后检出时转成 CRLF，使证据登记的字节摘要（取证输入清单、工具修订、R-P12 内联引用、fixtures 测试核对的旧实现锁定字节、源设计文档摘要）在重新克隆后失配。加 `-text` 后按原字节存取；没有改动任何文件内容，旧文件的工作区字节与 HEAD blob 相同（`git status` 不显示修改）。此修改发生在全部取证之后：取证输入清单中的 `.gitattributes` 与提交版本不同，差异只限这些追加行，任何测试都不读取这些行 |

提交范围（用户 2026-09-26 选定）：01 产物加 v2 设计文档。不含用户原有的 `README.md` 修改与 `docs/` 下 6 个旧文档的删除及乱码重命名。
