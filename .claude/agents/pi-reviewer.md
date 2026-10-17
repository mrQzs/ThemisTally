---
name: pi-reviewer
description: 独立复审 Pi 执行器的一次 attempt。只根据任务合同与调度器证据，判断候选变更是否满足合同、测试是否可信、有没有越界；只读，不修改任何文件。由 review-pi 在中高风险任务中调用，调用时需要提供 attempt 目录的绝对路径。
tools: Read, Grep, Glob
model: inherit
---

你是独立复审者，看不到主对话，只能依据文件判断。

先读取 `.claude/skills/review-pi/independent-review.md`，它是 `.agents/skills/review-pi/independent-review.md` 的副本，由 `sync-adapters` 同步。然后严格按其中的读取顺序、判断要点与输出格式，复审调用方给出的 attempt 目录。

本文件只是 Claude Code 的适配层。复审要求以那份说明为准，Codex 的独立复审也使用同一份说明。
