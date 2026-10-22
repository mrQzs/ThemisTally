// bun:ffi 的最小类型声明：只声明 native.ts 用到的那几样，免得为它引入 bun-types 依赖。
// 运行时只在 Bun 下动态 import（Node 下从不执行），见 native.ts。
declare module "bun:ffi" {
  export const FFIType: {
    readonly i32: number;
    readonly i64: number;
    readonly u32: number;
    readonly ptr: number;
  };
  export function ptr(view: ArrayBufferView): number;
  export const suffix: string;
  export function dlopen<T extends Record<string, { args: readonly number[]; returns: number }>>(
    path: string,
    symbols: T,
  ): { symbols: { [K in keyof T]: (...args: never[]) => number | bigint }; close(): void };
}
