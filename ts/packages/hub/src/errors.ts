// kit_hub.HubError：带退出码的报错（缺省 EXIT_FAIL）。
import { EXIT_FAIL } from "./constants.ts";

export class HubError extends Error {
  override readonly name = "HubError";
  readonly code: number;

  constructor(message: string, code: number = EXIT_FAIL) {
    super(message);
    this.code = code;
  }
}
