// 当前方案条（合同第 5 节）：SegmentedControl 选项为方案名，值本地选中（初值 active_preset，改选只改本地）；
// 选中的不是当前方案时 [切换…] 可点，走写确认流程；选中的就是当前方案时是禁用的普通 Button，不带提示；无方案时只写提示。
import { useState } from 'react';
import type { PresetsData } from '../../api';
import { Button, SegmentedControl } from '../../components';
import { useWriteFlow } from '../../writes/useWriteFlow';
import { WriteFlow } from '../../writes/WriteConfirmDialog';

export interface PresetBarProps {
  presets: PresetsData['presets'];
  active: string;
  reload?: () => Promise<void>;
}

export function PresetBar({ presets, active, reload }: PresetBarProps) {
  const [selected, setSelected] = useState(active);
  const { start, flow } = useWriteFlow(reload);
  if (presets.length === 0) {
    return <p className="rl-bar__empty">还没有方案：把当前的角色绑定存成方案，之后就能一键切换</p>;
  }
  const current = presets.find((p) => p.name === selected) ?? presets[0];
  const isCurrent = selected === active;
  const desc = isCurrent ? `当前：${active} · ${current.roles.length} 个角色` : `已选 ${selected}`;
  return (
    <div className="rl-bar">
      <SegmentedControl
        aria-label="当前方案"
        options={presets.map((p) => ({ value: p.name, label: p.name }))}
        value={selected}
        onChange={setSelected}
      />
      <span className="rl-bar__desc">{desc}</span>
      {isCurrent ? (
        <Button variant="primary" size="md" disabled>切换…</Button>
      ) : (
        <Button
          variant="primary"
          size="md"
          onClick={() => start({ action: 'preset.use', args: { name: selected }, title: `切换到方案 ${selected}？` })}
        >
          切换…
        </Button>
      )}
      <WriteFlow flow={flow} />
    </div>
  );
}
