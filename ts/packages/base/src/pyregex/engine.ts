// sre 的匹配器：CPython 3.12.10 Modules/_sre/sre_lib.h 的 SRE(match) 与 SRE(search) 的逐段移植（迁移第 ②b2 步）。
// 回溯用显式的上下文栈（与 sre 一样不递归），长行上的重复不会撑爆 JS 的调用栈。控制流照原样：DO_JUMP 压栈进入子模式，
// 子模式走到 SUCCESS 或失败就弹栈，回到对应的跳转标签接着做。与 sre 不同的只有不影响“有没有匹配”的部分：不记捕获组
// （MARK、lastmark），不做只为提速的预判（BRANCH 与 REPEAT_ONE 先看下一个字面量），toplevel 与 must_advance 恒为假
// （search 用不到）。
import { At, type FlatSet, MAX_CP, Op, type Program, flatContains } from "./compile.ts";
import { MAXREPEAT } from "./parser.ts";

const MAX_REPEAT = Number(MAXREPEAT);
const NEWLINE = 10;

const Jump = {
  NONE: 0,
  MAX_UNTIL_1: 1,
  MAX_UNTIL_2: 2,
  MAX_UNTIL_3: 3,
  MIN_UNTIL_1: 4,
  MIN_UNTIL_2: 5,
  MIN_UNTIL_3: 6,
  REPEAT: 7,
  REPEAT_ONE: 8,
  MIN_REPEAT_ONE: 9,
  BRANCH: 10,
  ASSERT: 11,
  ASSERT_NOT: 12,
  POSS_REPEAT_1: 13,
  POSS_REPEAT_2: 14,
  ATOMIC_GROUP: 15,
} as const;
type Jump = (typeof Jump)[keyof typeof Jump];

/** 执行到哪里：分派下一条指令，或者某个循环的开头（C 里是 for/while 回到条件处），或者退出当前上下文。 */
const Next = {
  DISPATCH: 0,
  EXIT: 1,
  BRANCH_LOOP: 2,
  REPEAT_ONE_LOOP: 3,
  MIN_REPEAT_ONE_LOOP: 4,
  MAX_UNTIL_TAIL: 5,
  POSS_REPEAT_MIN: 6,
  POSS_REPEAT_LOOP: 7,
  POSS_REPEAT_DONE: 8,
} as const;
type Next = (typeof Next)[keyof typeof Next];

/** SRE_REPEAT。 */
interface Repeat {
  count: number;
  readonly pc: number;
  readonly prev: Repeat | null;
  lastPtr: number;
}

/** SRE(match_context)：pc、ptr 是进入子模式之前的位置，saved 存 DATA_PUSH 的 last_ptr。 */
interface Context {
  pc: number;
  ptr: number;
  count: number;
  rep: Repeat | null;
  readonly jump: Jump;
  saved: number;
}

const newContext = (jump: Jump): Context => ({ pc: 0, ptr: 0, count: 0, rep: null, jump, saved: -1 });

/** SRE_IS_WORD 与 SRE_UNI_IS_WORD 用的集合。 */
export interface WordSets {
  readonly ascii: FlatSet;
  readonly unicode: FlatSet;
}

class Matcher {
  private ptr = 0;
  private readonly stack: Context[] = [];
  private readonly root = newContext(Jump.NONE);
  private repeat: Repeat | null = null;
  private readonly program: Program;
  private readonly text: Int32Array;
  private readonly words: WordSets;
  private readonly end: number;

  constructor(program: Program, text: Int32Array, words: WordSets) {
    this.program = program;
    this.text = text;
    this.words = words;
    this.end = text.length;
  }

  private isWord(index: number, unicode: boolean): boolean {
    return flatContains(unicode ? this.words.unicode : this.words.ascii, this.text[index] as number);
  }

  /** SRE(at)。 */
  private at(ptr: number, code: At): boolean {
    const { text, end } = this;
    switch (code) {
      case At.BEGINNING:
      case At.BEGINNING_STRING:
        return ptr === 0;
      case At.BEGINNING_LINE:
        return ptr === 0 || text[ptr - 1] === NEWLINE;
      case At.END:
        return (end - ptr === 1 && text[ptr] === NEWLINE) || ptr === end;
      case At.END_LINE:
        return ptr === end || text[ptr] === NEWLINE;
      case At.END_STRING:
        return ptr === end;
      case At.BOUNDARY:
      case At.NON_BOUNDARY:
      case At.UNI_BOUNDARY:
      case At.UNI_NON_BOUNDARY: {
        if (end === 0) return false;
        const unicode = code === At.UNI_BOUNDARY || code === At.UNI_NON_BOUNDARY;
        const thatp = ptr > 0 ? this.isWord(ptr - 1, unicode) : false;
        const thisp = ptr < end ? this.isWord(ptr, unicode) : false;
        return code === At.BOUNDARY || code === At.UNI_BOUNDARY ? thisp !== thatp : thisp === thatp;
      }
    }
  }

  /** SRE(count)：从 from 起，单字符的 item（CHAR <集合>）连续匹配几次，最多 maxcount 次。 */
  private count(itemPc: number, from: number, maxcount: number): number {
    const set = this.program.sets[this.program.code[itemPc + 1] as number] as FlatSet;
    let end = this.end;
    if (maxcount < end - from && maxcount !== MAX_REPEAT) end = from + maxcount;
    const text = this.text;
    let ptr = from;
    if (set.length === 2) {
      // 一段：直接比上下界
      const lo = set[0] as number;
      const hi = set[1] as number;
      while (ptr < end) {
        const cp = text[ptr] as number;
        if (cp < lo || cp > hi) break;
        ptr += 1;
      }
    } else if (set.length === 4 && set[0] === 0 && set[3] === MAX_CP && (set[1] as number) + 2 === set[2]) {
      // 只缺一个码点（. 就是“不是换行”）
      const excluded = (set[1] as number) + 1;
      while (ptr < end && text[ptr] !== excluded) ptr += 1;
    } else {
      while (ptr < end && flatContains(set, text[ptr] as number)) ptr += 1;
    }
    return ptr - from;
  }

  /** SRE(match)：从 this.ptr 开始匹配 startPc 起的字节码，走到最外层的 SUCCESS 为真。 */
  match(startPc: number): boolean {
    const code = this.program.code;
    const sets = this.program.sets;
    const text = this.text;
    const end = this.end;
    const stack = this.stack;
    stack.length = 0;
    let ctx = this.root;
    ctx.count = 0;
    ctx.rep = null;
    ctx.saved = -1;
    let pc = startPc;
    let ptr = this.ptr;
    let ret = false;
    let next: number = Next.DISPATCH; // 声明成 number：各分支互相改写，不让 TS 按赋值收窄
    // DO_JUMP 各处展开写（热循环里不用闭包，免得局部变量落到堆上）：ctx 记下 pc、ptr 压栈，换新的上下文，
    // pc 指向子模式，ptr 取 state->ptr（C 的 entrance）。失败与成功写成 ret 加 next = EXIT。

    for (;;) {
      switch (next) {
        case Next.EXIT: {
          const jump = ctx.jump;
          const parent = stack.pop();
          if (parent === undefined) return ret;
          ctx = parent;
          pc = ctx.pc;
          ptr = ctx.ptr;
          const rep = ctx.rep as Repeat;
          switch (jump) {
            case Jump.BRANCH:
              if (!ret) {
                pc += code[pc] as number;
                next = Next.BRANCH_LOOP;
              }
              break;
            case Jump.REPEAT_ONE:
              if (!ret) {
                ptr -= 1;
                ctx.count -= 1;
                next = Next.REPEAT_ONE_LOOP;
              }
              break;
            case Jump.MIN_REPEAT_ONE:
              if (!ret) {
                this.ptr = ptr;
                if (this.count(pc + 3, ptr, 1) === 0) {
                  ret = false;
                  next = Next.EXIT;
                } else {
                  ptr += 1;
                  ctx.count += 1;
                  next = Next.MIN_REPEAT_ONE_LOOP;
                }
              }
              break;
            case Jump.REPEAT:
              this.repeat = rep.prev;
              break;
            case Jump.MAX_UNTIL_1:
            case Jump.MIN_UNTIL_1:
              if (!ret) {
                rep.count = ctx.count - 1;
                this.ptr = ptr;
              }
              break;
            case Jump.MAX_UNTIL_2:
              rep.lastPtr = ctx.saved;
              if (!ret) {
                rep.count = ctx.count - 1;
                this.ptr = ptr;
                next = Next.MAX_UNTIL_TAIL;
              }
              break;
            case Jump.MAX_UNTIL_3:
              this.repeat = rep;
              if (!ret) this.ptr = ptr;
              break;
            case Jump.MIN_UNTIL_2: {
              this.repeat = rep;
              if (ret) break;
              this.ptr = ptr;
              const max = code[rep.pc + 2] as number;
              if ((ctx.count >= max && max !== MAX_REPEAT) || this.ptr === rep.lastPtr) break;
              rep.count = ctx.count;
              ctx.saved = rep.lastPtr; // 空匹配保护
              rep.lastPtr = this.ptr;
              ctx.pc = pc;
              ctx.ptr = ptr;
              stack.push(ctx);
              ctx = newContext(Jump.MIN_UNTIL_3);
              pc = rep.pc + 3;
              ptr = this.ptr;
              next = Next.DISPATCH;
              break;
            }
            case Jump.MIN_UNTIL_3:
              rep.lastPtr = ctx.saved;
              if (!ret) {
                rep.count = ctx.count - 1;
                this.ptr = ptr;
              }
              break;
            case Jump.POSS_REPEAT_1:
              if (ret) {
                ctx.count += 1;
                next = Next.POSS_REPEAT_MIN;
              } else {
                this.ptr = ptr;
                this.repeat = rep.prev;
              }
              break;
            case Jump.POSS_REPEAT_2:
              if (ret) {
                ctx.count += 1;
                next = Next.POSS_REPEAT_LOOP;
              } else {
                this.ptr = ptr;
                next = Next.POSS_REPEAT_DONE;
              }
              break;
            case Jump.ATOMIC_GROUP:
              if (!ret) {
                this.ptr = ptr;
              } else {
                pc += code[pc] as number;
                ptr = this.ptr;
                next = Next.DISPATCH;
              }
              break;
            case Jump.ASSERT:
              if (ret) {
                pc += code[pc] as number;
                next = Next.DISPATCH;
              }
              break;
            case Jump.ASSERT_NOT:
              if (ret) {
                ret = false;
              } else {
                pc += code[pc] as number;
                next = Next.DISPATCH;
              }
              break;
            case Jump.NONE:
              break;
          }
          // 没有改 next 的分支：带着 ret 继续退出
          continue;
        }

        case Next.BRANCH_LOOP:
          // 分支的第一条是单字符、当前字符又不符：跳过这个分支（sre 对 LITERAL 与 IN 做同样的预判）
          while (
            code[pc] !== 0 &&
            code[pc + 1] === Op.CHAR &&
            (ptr >= end || !flatContains(sets[code[pc + 2] as number] as FlatSet, text[ptr] as number))
          ) {
            pc += code[pc] as number;
          }
          if (code[pc] === 0) {
            ret = false;
            next = Next.EXIT;
          } else {
            this.ptr = ptr;
            ctx.pc = pc;
            ctx.ptr = ptr;
            stack.push(ctx);
            ctx = newContext(Jump.BRANCH);
            pc += 1;
            ptr = this.ptr;
            next = Next.DISPATCH;
          }
          continue;

        case Next.REPEAT_ONE_LOOP: {
          const min = code[pc + 1] as number;
          const tail = pc + (code[pc] as number);
          if (code[tail] === Op.CHAR) {
            // 尾部以单字符开头：先退到它能匹配的位置（sre 对 LITERAL 做的预判，推广到任意单字符，结果相同）
            const set = sets[code[tail + 1] as number] as FlatSet;
            if (set.length === 2 && set[0] === set[1]) {
              const literal = set[0] as number;
              while (ctx.count >= min && (ptr >= end || text[ptr] !== literal)) {
                ptr -= 1;
                ctx.count -= 1;
              }
            } else {
              while (ctx.count >= min && (ptr >= end || !flatContains(set, text[ptr] as number))) {
                ptr -= 1;
                ctx.count -= 1;
              }
            }
          }
          if (ctx.count >= min) {
            this.ptr = ptr;
            ctx.pc = pc;
            ctx.ptr = ptr;
            stack.push(ctx);
            ctx = newContext(Jump.REPEAT_ONE);
            pc = tail;
            ptr = this.ptr;
            next = Next.DISPATCH;
          } else {
            ret = false;
            next = Next.EXIT;
          }
          continue;
        }

        case Next.MIN_REPEAT_ONE_LOOP: {
          const max = code[pc + 2] as number;
          if (max === MAX_REPEAT || ctx.count <= max) {
            this.ptr = ptr;
            ctx.pc = pc;
            ctx.ptr = ptr;
            stack.push(ctx);
            ctx = newContext(Jump.MIN_REPEAT_ONE);
            pc += code[pc] as number;
            ptr = this.ptr;
            next = Next.DISPATCH;
          } else {
            ret = false;
            next = Next.EXIT;
          }
          continue;
        }

        case Next.MAX_UNTIL_TAIL:
          this.repeat = (ctx.rep as Repeat).prev;
          ctx.pc = pc;
          ctx.ptr = ptr;
          stack.push(ctx);
          ctx = newContext(Jump.MAX_UNTIL_3);
          ptr = this.ptr;
          next = Next.DISPATCH;
          continue;

        case Next.POSS_REPEAT_MIN:
          if (ctx.count < (code[pc + 1] as number)) {
            ctx.pc = pc;
            ctx.ptr = ptr;
            stack.push(ctx);
            ctx = newContext(Jump.POSS_REPEAT_1);
            pc += 3;
            ptr = this.ptr;
            next = Next.DISPATCH;
          } else {
            ptr = -1; // 让下面的循环至少进入一次
            next = Next.POSS_REPEAT_LOOP;
          }
          continue;

        case Next.POSS_REPEAT_LOOP: {
          const max = code[pc + 2] as number;
          if ((ctx.count < max || max === MAX_REPEAT) && this.ptr !== ptr) {
            ptr = this.ptr; // 空匹配保护：这一轮没有前进就停
            ctx.pc = pc;
            ctx.ptr = ptr;
            stack.push(ctx);
            ctx = newContext(Jump.POSS_REPEAT_2);
            pc += 3;
            ptr = this.ptr;
            next = Next.DISPATCH;
          } else {
            next = Next.POSS_REPEAT_DONE;
          }
          continue;
        }

        case Next.POSS_REPEAT_DONE:
          this.repeat = (ctx.rep as Repeat).prev;
          pc += (code[pc] as number) + 1;
          ptr = this.ptr;
          next = Next.DISPATCH;
          continue;

        case Next.DISPATCH:
          break;
      }

      const op = code[pc++] as Op;
      switch (op) {
        case Op.FAILURE:
          ret = false;
          next = Next.EXIT;
          break;

        case Op.SUCCESS:
          this.ptr = ptr;
          ret = true;
          next = Next.EXIT;
          break;

        case Op.CHAR:
          if (ptr >= end || !flatContains(sets[code[pc] as number] as FlatSet, text[ptr] as number)) {
            ret = false;
            next = Next.EXIT;
          } else {
            pc += 1;
            ptr += 1;
          }
          break;

        case Op.AT:
          if (this.at(ptr, code[pc] as At)) {
            pc += 1;
          } else {
            ret = false;
            next = Next.EXIT;
          }
          break;

        case Op.JUMP:
          pc += code[pc] as number;
          break;

        case Op.BRANCH:
          next = Next.BRANCH_LOOP;
          break;

        case Op.REPEAT_ONE: {
          // <REPEAT_ONE> <skip> <1=min> <2=max> item <SUCCESS> tail
          const min = code[pc + 1] as number;
          if (min > end - ptr) {
            ret = false;
            next = Next.EXIT;
            break;
          }
          this.ptr = ptr;
          ctx.count = this.count(pc + 3, ptr, code[pc + 2] as number);
          ptr += ctx.count;
          if (ctx.count < min) {
            ret = false;
            next = Next.EXIT;
            break;
          }
          if (code[pc + (code[pc] as number)] === Op.SUCCESS && ptr === end) {
            this.ptr = ptr; // 尾部是空的
            ret = true;
            next = Next.EXIT;
            break;
          }
          next = Next.REPEAT_ONE_LOOP;
          break;
        }

        case Op.MIN_REPEAT_ONE: {
          const min = code[pc + 1] as number;
          if (min > end - ptr) {
            ret = false;
            next = Next.EXIT;
            break;
          }
          this.ptr = ptr;
          if (min === 0) {
            ctx.count = 0;
          } else {
            const counted = this.count(pc + 3, ptr, min);
            if (counted < min) {
              ret = false;
              next = Next.EXIT;
              break;
            }
            ctx.count = counted;
            ptr += counted;
          }
          if (code[pc + (code[pc] as number)] === Op.SUCCESS) {
            this.ptr = ptr;
            ret = true;
            next = Next.EXIT;
            break;
          }
          next = Next.MIN_REPEAT_ONE_LOOP;
          break;
        }

        case Op.POSSESSIVE_REPEAT_ONE: {
          const min = code[pc + 1] as number;
          if (ptr + min > end) {
            ret = false;
            next = Next.EXIT;
            break;
          }
          this.ptr = ptr;
          ctx.count = this.count(pc + 3, ptr, code[pc + 2] as number);
          ptr += ctx.count;
          if (ctx.count < min) {
            ret = false;
            next = Next.EXIT;
            break;
          }
          pc += code[pc] as number;
          if (code[pc] === Op.SUCCESS && ptr === end) {
            this.ptr = ptr;
            ret = true;
            next = Next.EXIT;
          }
          break;
        }

        case Op.REPEAT: {
          // <REPEAT> <skip> <1=min> <2=max> item <UNTIL> tail
          const rep: Repeat = { count: -1, pc, prev: this.repeat, lastPtr: -1 };
          ctx.rep = rep;
          this.repeat = rep;
          this.ptr = ptr;
          ctx.pc = pc;
          ctx.ptr = ptr;
          stack.push(ctx);
          ctx = newContext(Jump.REPEAT);
          pc = pc + (code[pc] as number);
          ptr = this.ptr;
          next = Next.DISPATCH;
          break;
        }

        case Op.MAX_UNTIL: {
          const rep = this.repeat as Repeat;
          ctx.rep = rep;
          this.ptr = ptr;
          ctx.count = rep.count + 1;
          if (ctx.count < (code[rep.pc + 1] as number)) {
            rep.count = ctx.count; // 次数还不够
            ctx.pc = pc;
            ctx.ptr = ptr;
            stack.push(ctx);
            ctx = newContext(Jump.MAX_UNTIL_1);
            pc = rep.pc + 3;
            ptr = this.ptr;
            next = Next.DISPATCH;
            break;
          }
          const max = code[rep.pc + 2] as number;
          if ((ctx.count < max || max === MAX_REPEAT) && this.ptr !== rep.lastPtr) {
            rep.count = ctx.count;
            ctx.saved = rep.lastPtr; // 空匹配保护
            rep.lastPtr = this.ptr;
            ctx.pc = pc;
            ctx.ptr = ptr;
            stack.push(ctx);
            ctx = newContext(Jump.MAX_UNTIL_2);
            pc = rep.pc + 3;
            ptr = this.ptr;
            next = Next.DISPATCH;
            break;
          }
          next = Next.MAX_UNTIL_TAIL;
          break;
        }

        case Op.MIN_UNTIL: {
          const rep = this.repeat as Repeat;
          ctx.rep = rep;
          this.ptr = ptr;
          ctx.count = rep.count + 1;
          if (ctx.count < (code[rep.pc + 1] as number)) {
            rep.count = ctx.count;
            ctx.pc = pc;
            ctx.ptr = ptr;
            stack.push(ctx);
            ctx = newContext(Jump.MIN_UNTIL_1);
            pc = rep.pc + 3;
            ptr = this.ptr;
            next = Next.DISPATCH;
            break;
          }
          this.repeat = rep.prev; // 先试尾部
          ctx.pc = pc;
          ctx.ptr = ptr;
          stack.push(ctx);
          ctx = newContext(Jump.MIN_UNTIL_2);
          ptr = this.ptr;
          next = Next.DISPATCH;
          break;
        }

        case Op.POSSESSIVE_REPEAT: {
          // <POSSESSIVE_REPEAT> <skip> <1=min> <2=max> pattern <SUCCESS> tail
          this.ptr = ptr;
          const rep: Repeat = { count: -1, pc: -1, prev: this.repeat, lastPtr: -1 };
          ctx.rep = rep;
          this.repeat = rep;
          ctx.count = 0;
          next = Next.POSS_REPEAT_MIN;
          break;
        }

        case Op.ATOMIC_GROUP:
          // <ATOMIC_GROUP> <skip> pattern <SUCCESS> tail
          this.ptr = ptr;
          ctx.pc = pc;
          ctx.ptr = ptr;
          stack.push(ctx);
          ctx = newContext(Jump.ATOMIC_GROUP);
          pc = pc + 1;
          ptr = this.ptr;
          next = Next.DISPATCH;
          break;

        case Op.ASSERT: {
          // <ASSERT> <skip> <back> <pattern>
          const back = code[pc + 1] as number;
          if (ptr < back) {
            ret = false;
            next = Next.EXIT;
            break;
          }
          this.ptr = ptr - back;
          ctx.pc = pc;
          ctx.ptr = ptr;
          stack.push(ctx);
          ctx = newContext(Jump.ASSERT);
          pc = pc + 2;
          ptr = this.ptr;
          next = Next.DISPATCH;
          break;
        }

        case Op.ASSERT_NOT: {
          const back = code[pc + 1] as number;
          if (ptr >= back) {
            this.ptr = ptr - back;
            ctx.pc = pc;
            ctx.ptr = ptr;
            stack.push(ctx);
            ctx = newContext(Jump.ASSERT_NOT);
            pc = pc + 2;
            ptr = this.ptr;
            next = Next.DISPATCH;
          } else {
            pc += code[pc] as number;
          }
          break;
        }

        default:
          throw new Error(`sre: 未知的指令 ${String(op)}`);
      }
    }
  }

  /** 在 start 处试一次（search 的一个起点）。 */
  tryAt(start: number): boolean {
    this.ptr = start;
    this.repeat = null;
    return this.match(0);
  }
}

/** SRE(search)：整行里有没有一处匹配。信息块里的最小宽度、字面量前缀、字符集前缀照 sre 用来挑起点。 */
export function search(program: Program, text: Int32Array, words: WordSets): boolean {
  const end = text.length;
  const { minWidth, prefix, charset, code } = program;
  if (minWidth && end < minWidth) return false;
  const matcher = new Matcher(program, text, words);
  if (prefix.length > 0) {
    // 字面量前缀：只在前缀出现的位置尝试（与 sre 的逐字比较、重叠表等价）
    const first = prefix[0] as number;
    for (let ptr = 0; ptr + prefix.length <= end; ptr += 1) {
      if (text[ptr] !== first) continue;
      let index = 1;
      while (index < prefix.length && text[ptr + index] === prefix[index]) index += 1;
      if (index === prefix.length && matcher.tryAt(ptr)) return true;
    }
    return false;
  }
  if (charset !== null) {
    for (let ptr = 0; ptr < end; ptr += 1) {
      if (flatContains(charset, text[ptr] as number) && matcher.tryAt(ptr)) return true;
    }
    return false;
  }
  // 一般情形：最小宽度大于 1 时，末尾放不下的起点不试；以 ^ 或 \A 开头时只试开头
  const anchored = code[0] === Op.AT && (code[1] === At.BEGINNING || code[1] === At.BEGINNING_STRING);
  const last = anchored ? 0 : minWidth > 1 ? Math.max(0, end - (minWidth - 1)) : end;
  const leading = program.leading;
  for (let ptr = 0; ptr <= last; ptr += 1) {
    // 第一个字符就对不上的起点，试了也是失败
    if (leading !== null && (ptr >= end || !flatContains(leading, text[ptr] as number))) continue;
    if (matcher.tryAt(ptr)) return true;
  }
  return false;
}
