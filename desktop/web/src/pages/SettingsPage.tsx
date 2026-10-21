// 外壳设置页（src/pages/SettingsPage.tsx）：用 PageFrame 的外壳设置页。数据来自桩的 getState，不看 ?mock=（K5）；
// ?mock=offline 时 PageFrame 仍显示断线横幅与「可能已过期」（已知差异 H11）。load 是 useCallback 包的 getState 加一层 .then
// （依赖只有 shell，不加 await；信封类型从 PageFrameProps 推出，不 import api.ts；command 写 themisShell.getState）。
import { useCallback } from 'react';
import { PageFrame, type PageFrameProps } from '../shell/PageFrame';
import type { ShellState } from '../shellpages/themisShell';
import { useThemisShell } from '../shellpages/shellContext';
import { SettingsView } from '../shellpages/SettingsView';

type ShellEnvelope = Awaited<ReturnType<PageFrameProps<ShellState>['load']>>;

export default function SettingsPage() {
  const shell = useThemisShell('ready');
  const load = useCallback(
    (): Promise<ShellEnvelope> =>
      shell.getState().then((data) => ({
        ok: true,
        exit_code: 0,
        data,
        output: [],
        messages: [],
        command: ['themisShell.getState'],
        elapsed_ms: 0,
      })),
    [shell],
  );
  return (
    <PageFrame<ShellState>
      title="设置"
      description="设置保存在桌面应用自己的用户数据目录里，不写进仓库的配置"
      load={load}
    >
      {(data) => <SettingsView data={data} shell={shell} />}
    </PageFrame>
  );
}
