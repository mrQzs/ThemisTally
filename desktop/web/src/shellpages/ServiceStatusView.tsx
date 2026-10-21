// 服务状态与恢复视图（src/shellpages/ServiceStatusView.tsx）：整页卡片（结构照断线画布 :362–368），宽 440 居中。
// ServerCrashIcon 32 + h1「本机服务已停止」+ 退出码行 + 一段说明（共用 exitCodes.ts）+ [重启服务] + [打开设置]。
// 只有点了重启、之后收到 running 才跳回服务窗口（K15）；直接打开按当前状态显示。不设 role=alert。
import { useEffect, useRef, useState } from 'react';
import { Button } from '../components';
import { ServerCrashIcon } from '../icons';
import { RefreshCwIcon } from '../icons/frame';
import type { ServiceState, ThemisShell } from './themisShell';
import { stoppedNote } from './exitCodes';
import { clock } from './format';
import './service-status.css';

export interface ServiceStatusViewProps {
  shell: ThemisShell;
  navigate: (path: string) => void;
}

export function ServiceStatusView({ shell, navigate }: ServiceStatusViewProps) {
  const [service, setService] = useState<ServiceState>({ kind: 'idle' });
  const [restarting, setRestarting] = useState(false);
  const awaitingRef = useRef(false);

  useEffect(() => {
    document.title = '本机服务已停止 · Themis Tally';
  }, []);

  // 订阅 service-state 再读 getState；点重启后收到 running 才跳回，收到 exited 换新退出码并恢复。
  useEffect(() => {
    const off = shell.on('service-state', (svc) => {
      setService(svc);
      if (svc.kind === 'running') {
        setRestarting(false);
        if (awaitingRef.current) {
          awaitingRef.current = false;
          navigate('/overview');
        }
      } else if (svc.kind === 'exited') {
        setRestarting(false);
        awaitingRef.current = false;
      }
    });
    shell.getState().then((st) => setService(st.service)).catch(() => {});
    return off;
  }, [shell, navigate]);

  const onRestart = () => {
    awaitingRef.current = true;
    setRestarting(true);
    shell.restartService();
  };

  const exited = service.kind === 'exited';
  const code = exited ? String(service.exitCode) : '—';
  const at = exited ? service.at : Date.now();
  const note = stoppedNote(exited ? service.exitCode : 0);

  return (
    <section className="tt-ss">
      <ServerCrashIcon width={32} height={32} className="tt-ss__icon" />
      <h1 className="tt-ss__title">本机服务已停止</h1>
      <p className="tt-ss__line">
        退出码 <code className="tt-ss__code" data-exit-code>{code}</code> · {clock(at)}。重启后会重新读取数据。
      </p>
      <p className="tt-ss__note">{note}</p>
      <Button variant="primary" size="lg" loading={restarting} loadingText="正在重启…" onClick={onRestart}>
        <RefreshCwIcon width={16} height={16} />
        重启服务
      </Button>
      <Button variant="secondary" size="lg" onClick={() => navigate('/settings')}>
        打开设置
      </Button>
    </section>
  );
}
