// 表单底部的实时内核预览（合同第三节）：表单合法才在 300ms 防抖后调 preview；迟到的回应按序号丢弃。
// 只读演示数据，不联网。
import { useEffect, useRef, useState } from 'react';
import { preview, type HttpReply, type PreviewData, type WriteAction, type WriteArgs } from '../api';

// 防抖：每次取值改动后等 300ms 才发预览，把连续改动合并成一次。
const DEBOUNCE_MS = 300;

export interface LivePreview {
  /** 这次预览对应的取值键（JSON.stringify(args)）：用来判断预览是否还对应当前取值。 */
  key: string;
  /** 状态码 200 且信封 ok 为真。 */
  ok: boolean;
  /** 去掉 --dry-run 与 --json 的命令。 */
  command: string[];
  /** 警告行（预览原文）。 */
  warnings: string[];
  /** 报错行（预览原文）；没有报错时为 null。 */
  error: string | null;
}

function fromReply(key: string, reply: HttpReply<PreviewData>): LivePreview {
  const data = reply.body.data;
  const ok = reply.status === 200 && reply.body.ok;
  const messages = reply.body.messages ?? [];
  return {
    key,
    ok,
    command: data ? data.command.filter((a) => a !== '--dry-run' && a !== '--json') : [],
    warnings: data?.warnings ?? [],
    error: ok ? null : messages.length > 0 ? messages.join('\n') : '预览失败：服务没有回应',
  };
}

/**
 * 底部实时预览。enabled 为真（表单合法）时才在 300ms 防抖后调 preview；表单不合法时不调。
 * 每次请求带自增序号，回来时序号不是最新的就丢掉（迟到的回应不覆盖底部）。
 * current 表示最近一次预览还对应当前取值（result.key 等于当前 args 的键），供 [确认…] 门控。
 */
export function useLivePreview(
  action: WriteAction,
  args: WriteArgs,
  enabled: boolean,
): { result: LivePreview | null; current: boolean } {
  const key = JSON.stringify(args);
  const [result, setResult] = useState<LivePreview | null>(null);
  const seqRef = useRef(0);

  useEffect(() => {
    if (!enabled) return;
    const my = (seqRef.current += 1);
    const timer = setTimeout(() => {
      preview(action, args).then(
        (reply) => {
          if (my === seqRef.current) setResult(fromReply(key, reply));
        },
        () => {
          if (my === seqRef.current) {
            setResult({ key, ok: false, command: [], warnings: [], error: '预览失败：服务没有回应' });
          }
        },
      );
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
    // args 用序列化后的 key 参与依赖：内容没变就不重新发起；enabled 关时不清结果，由调用方按取值是否合法来展示。
  }, [action, key, enabled]);

  return { result, current: result !== null && result.key === key };
}
