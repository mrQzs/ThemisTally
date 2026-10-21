// 当前方案条（合同第 5 节）：SegmentedControl 选项为方案名，值本地选中（初值 active_preset，改选只改本地）；
// 说明两种文字；[切换…] 始终禁用；无方案时只写提示，不渲染分段与 [切换…]。
import { useState } from 'react';
import type { PresetsData } from '../../api';
import { SegmentedControl } from '../../components';
import { DisabledAction } from '../../shell/DisabledAction';

export interface PresetBarProps {
  presets: PresetsData['presets'];
  active: string;
}

export function PresetBar({ presets, active }: PresetBarProps) {
  const [selected, setSelected] = useState(active);
  if (presets.length === 0) {
    return <p className="rl-bar__empty">还没有方案：把当前的角色绑定存成方案，之后就能一键切换</p>;
  }
  const current = presets.find((p) => p.name === selected) ?? presets[0];
  const desc =
    selected === active
      ? `当前：${active} · ${current.roles.length} 个角色`
      : `已选 ${selected} · 切换在第二阶段接入`;
  return (
    <div className="rl-bar">
      <SegmentedControl
        aria-label="当前方案"
        options={presets.map((p) => ({ value: p.name, label: p.name }))}
        value={selected}
        onChange={setSelected}
      />
      <span className="rl-bar__desc">{desc}</span>
      <DisabledAction label="切换…" variant="primary" size="md" />
    </div>
  );
}
