# 01 续接独立复审记录

日期：2026-09-26。审查方式是当前线程内独立子代理，不是 Pi 派遣、review-pi 或 codex exec 记录。

## 代码复审

代码审查者没有修改实现或测试。范围：baseline.py、protocols.py、sealing.py、基准工具测试及 Windows 重解析点测试；另抽查 fixture 两份生成/测试代码的差异。

- 找到 B-01：lstat 权限错误及打开后类型变化可被标为完整采样。独立纯内存复现修前 complete=true、baseline_consistent=true；主代理修复后同样复现得到 complete=false、baseline_consistent=null。
- 找到 B-02：capture-id 的 match/$ 接受末尾 LF；改为 fullmatch，回归覆盖尾 LF 与长度边界。
- 核对 TempArea 绑定创建路径并复用共享所有权核验。路径篡改、marker 篡改测试覆盖缺口。
- 核对 Windows 文本前缀断言已移入各自 subTest，不再跨可能跳过的子测试索引 texts。
- 完整复跑发现 ImportSideEffectTests 的空目录断言与新增 marker 冲突；适配后同时比较导入前后条目和已有字节，原禁止进程、禁止加载监督器、源码目录条目不变的检查保留，未弱化导入约束。
- 最终工作树差异未发现新的重要问题。旧实现和 Schema 的“不变”结论以主代理的逐字节核对与取证清单为证，不由代码审阅推断。

## 最终文档与证据复审

另一审查者参与过 baseline-report 两份文件的历史/当前指针整理；本节最终核对只读，没有改写归档或运行整套测试。

复核当前 completion-review.md、README.md、verification-summary.json 和归档输出：

1. 七组 unittest 可复算为 623 个方法、616 通过、7 跳过、0 失败；十组被测命令退出 0，capture complete 且前后一致。
2. 旧自测 256 checks / 0 failed，兼容比对 40 checks / 0 differ，stub 重生成 10 checks / 0 differ。
3. 协议四个跳过、POSIX 三个跳过均逐项保留；Schema 元校验在协议归档为 ok，源码确执行 Draft202012Validator.check_schema 和文档样例校验。
4. 初次基准组的退出1、45 tests / 1 failure 与目录 marker 冲突解释相符；最终基准组45项通过，失败记录单独保留。
5. 11份 archive-manifest 的长度/摘要与汇总引用一致；抽验协议、fixture、baseline 三组 capture/stdout/stderr，共9个文件摘要一致。主代理另逐项核对869个归档文件。
6. 历史修订7、两次不同输入闭包、当前指针及网络隔离限制说明准确；A15未记PASS，02+能力未冒称实现。

结论：当前验收说明与十组最终取证及首次失败归档一致，未发现将跳过计为通过、将历史照录当作当前判定，或将跨平台及后续模块能力冒称完成。模块01可在已声明的Windows与阶段职责范围内验收；A15和明确的后续能力限制继续保留。此结论基于归档与源码抽验，没有独立重跑整套测试。
