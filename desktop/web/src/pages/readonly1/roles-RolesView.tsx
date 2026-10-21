// 角色与模型视图（合同第 5 节）：当前方案条、角色卡两列网格、profile 表、方案表与差异面板。
// 只收数据与回调（onDiff 由页面提供，视图不调 api）。
import type { Envelope, PresetDiffData, PresetsData, ProfilesData, RolesData } from '../../api';
import { RoleCard } from './roles-RoleCard';
import { PresetBar } from './roles-PresetBar';
import { ProfilesTable } from './roles-ProfilesTable';
import { PresetsTable } from './roles-PresetsTable';
import { normalizeRole } from './roles-logic';
// 样式表接线（终审 B1）：放在组件 import 之后，使本表晚于 common-section.css 载入。
import './roles-styles.css';

export interface RolesViewData {
  roles: RolesData;
  profiles: ProfilesData;
  presets: PresetsData;
}

export interface RolesViewProps {
  data: RolesViewData;
  onDiff: (a: string, b: string) => Promise<Envelope<PresetDiffData>>;
}

export function RolesView({ data, onDiff }: RolesViewProps) {
  const active = data.presets.active_preset;
  const roleInfos = data.roles.roles.map(normalizeRole);
  const activePreset = data.presets.presets.find((p) => p.name === active);
  const totalRoles = activePreset ? activePreset.roles.length : 0;
  return (
    <div className="rl" data-page="roles">
      <PresetBar presets={data.presets.presets} active={active} />
      <div className="rl-grid tt-grid-2">
        {roleInfos.map((r) => (
          <RoleCard key={r.role} role={r} activePreset={active} />
        ))}
      </div>
      <ProfilesTable profiles={data.profiles.profiles} roles={roleInfos} />
      {data.presets.presets.length > 0 && (
        <PresetsTable presets={data.presets.presets} active={active} totalRoles={totalRoles} onDiff={onDiff} />
      )}
    </div>
  );
}
