// 角色与模型页（合同第 2、5 条）：并行读 getRoles/getProfiles/getPresets，任一失败按 roles→profiles→presets 顺序返回第一个失败信封；
// 不传 isEmpty（?mock=empty 时仍 data）；差异读取经 onDiff 回调（页面持 diffPresets，视图不调 api）。
import { PageFrame } from '../shell/PageFrame';
import { DisabledAction } from '../shell/DisabledAction';
import {
  diffPresets,
  getPresets,
  getProfiles,
  getRoles,
  type Envelope,
  type PresetDiffData,
  type PresetsData,
  type ProfilesData,
  type RolesData,
} from '../api';
import { RolesView, type RolesViewData } from './readonly1/roles-RolesView';

const loadRoles = (): Promise<Envelope<RolesViewData>> =>
  Promise.all([getRoles(), getProfiles(), getPresets()]).then(([roles, profiles, presets]) => {
    const firstBad = [roles, profiles, presets].find((e) => !e.ok || e.data == null);
    if (firstBad) return firstBad as unknown as Envelope<RolesViewData>;
    return {
      ok: true,
      exit_code: 0,
      data: { roles: roles.data as RolesData, profiles: profiles.data as ProfilesData, presets: presets.data as PresetsData },
      output: [],
      messages: [],
      command: roles.command,
      elapsed_ms: 0,
    };
  });

export default function RolesPage() {
  return (
    <PageFrame<RolesViewData>
      title="角色与模型"
      description="四个角色各用哪个 CLI 与模型；方案可以一键切换"
      load={loadRoles}
      actions={
        <>
          <DisabledAction label="保存当前为方案…" />
          <DisabledAction label="新建 profile" />
        </>
      }
    >
      {(data) => <RolesView data={data} onDiff={diffPresets} />}
    </PageFrame>
  );
}
