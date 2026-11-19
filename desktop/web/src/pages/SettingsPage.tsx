// 外壳设置页（src/pages/SettingsPage.tsx）：服务窗口里经宿主接口打开设置外壳窗口；外壳页窗口与开发、桩模式照旧显示原来的设置页。
// 有没有宿主接口在每次渲染时判一次（不缓存）：服务窗口的 preload 暴露它，外壳页窗口的 preload 不暴露。
import { useCallback, useEffect, useState } from 'react';
import { PageFrame, type PageFrameProps } from '../shell/PageFrame';
import type { ShellState } from '../shellpages/themisShell';
import { useThemisShell } from '../shellpages/shellContext';
import { SettingsView } from '../shellpages/SettingsView';
import { hostHasOpenSettings, hostOpenSettings } from '../live/hostSettings';

type ShellEnvelope = Awaited<ReturnType<PageFrameProps<ShellState>['load']>>;

// 旧分支：外壳页窗口与开发、桩模式下照旧渲染的设置页，渲染与 hook 一字不改。
function ShellSettingsPage() {
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

// 新分支的数据：服务窗口经宿主接口开设置外壳窗口，本页没有可读的设置数据，用空形状占位。
interface HostSettingsData {
  opened: boolean;
}

type HostEnvelopeFrame = Awaited<ReturnType<PageFrameProps<HostSettingsData>['load']>>;

function HostSettingsPage() {
  const [reason, setReason] = useState<string | null>(null);
  const load = useCallback(
    (): Promise<HostEnvelopeFrame> =>
      Promise.resolve({
        ok: true,
        exit_code: 0,
        data: { opened: true },
        output: [],
        messages: [],
        command: ['host.openSettings'],
        elapsed_ms: 0,
      }),
    [],
  );
  // 挂载时开一次设置外壳窗口；点按钮再开一次（已经开着就聚焦那一个）。
  const open = useCallback(() => {
    const pending = hostOpenSettings();
    if (pending === null) {
      setReason('unavailable');
      return;
    }
    pending
      .then((env) => {
        if (env && env.ok === true) setReason(null);
        else setReason((env && env.reason) || 'failed');
      })
      .catch(() => setReason('internal'));
  }, []);
  useEffect(() => {
    open();
  }, [open]);
  return (
    <PageFrame<HostSettingsData>
      title="设置"
      description="设置保存在桌面应用自己的用户数据目录里，不写进仓库的配置"
      load={load}
    >
      {() => (
        <div>
          <p>设置在一个单独的窗口里打开；改动保存后下次起服务才生效。</p>
          {reason !== null && <p role="alert">{`打开设置失败：${reason}`}</p>}
          <button type="button" onClick={open}>
            打开设置
          </button>
        </div>
      )}
    </PageFrame>
  );
}

export default function SettingsPage() {
  return hostHasOpenSettings() ? <HostSettingsPage /> : <ShellSettingsPage />;
}
