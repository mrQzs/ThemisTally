// 七端的交差工具（七端改造第 1 条，第 90 轮）：pi 工人用 `--extension <这个文件>` 加载，调用一次 deliver 交差。
// 参数格式是内核给的 JSON Schema（环境变量 THEMIS_DELIVER_SCHEMA 指向 scripts/hub/schemas/<岗位>.json）：pi 先按它校验，
// 不合格当场退回，模型在同一回合里重交；合格之后把校验过的参数原样放进 details，回合随即结束（terminate）。
// 内核从自己截下的事件流里读 tool_execution_end 的 details，再用同一份 schema 复核一遍，不读会话文件。
// 这个文件与 schema 都在内核目录里，算内核文件：内核起 pi 之前核对它们的哈希，被改过就不起。
import { readFileSync } from "node:fs";
import { Type } from "@earendil-works/pi-ai";
import { defineTool, type ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default function (pi: ExtensionAPI): void {
  const schemaPath = process.env["THEMIS_DELIVER_SCHEMA"];
  if (!schemaPath) throw new Error("THEMIS_DELIVER_SCHEMA 没有设：内核起工人时会给");
  const schema = JSON.parse(readFileSync(schemaPath, "utf8")) as Record<string, unknown>;
  pi.registerTool(defineTool({
    name: "deliver",
    label: "Deliver",
    description: "交差：把这一回合的结果按参数格式交给内核。整回合只调用一次，调用之后这一回合就结束；"
      + "不要再在消息里写 json 代码块，内核不读它。",
    parameters: Type.Unsafe<Record<string, unknown>>(schema),
    async execute(_toolCallId, params) {
      return { content: [{ type: "text", text: "内核已收到，这一回合到此结束。" }], details: params, terminate: true };
    },
  }));
}
