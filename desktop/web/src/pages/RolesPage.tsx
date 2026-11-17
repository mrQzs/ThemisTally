// 角色与模型页（合同第 2、5 条）：并行读 getRoles/getProfiles/getPresets，任一失败按 roles→profiles→presets 顺序返回第一个失败信封；
// 不传 isEmpty（?mock=empty 时仍 data）；差异读取经 onDiff 回调（页面持 diffPresets，视图不调 api）。
import { useEffect, useState } from 'react';
import { PageFrame } from '../shell/PageFrame';
import { DisabledAction } from '../shell/DisabledAction';
import {
  diffPresets,
  getPresets,
  getProfiles,
  getRoles,
  getHubRoles,
  getQuizsLive,
  type Envelope,
  type HubRolesData,
  type PresetDiffData,
  type PresetsData,
  type ProfilesData,
  type QuizsLiveData,
  type RolesData,
} from '../api';
import { RolesView, type RolesViewData } from './readonly1/roles-RolesView';
import { NewProfileAction } from '../writes/ProfileForm';

// 并行读四个：前三个（roles/profiles/presets）里第一个坏的按 roles→profiles→presets 顺序整页返回那个失败信封；
// hub 的信封整个放进 data.hub，不参与整页失败判定（hub 读失败只在七端岗位那一组显示）。
const loadRoles = (): Promise<Envelope<RolesViewData>> =>
  Promise.all([getRoles(), getProfiles(), getPresets(), getHubRoles()]).then(([roles, profiles, presets, hub]) => {
    const firstBad = [roles, profiles, presets].find((e) => !e.ok || e.data == null);
    if (firstBad) return firstBad as unknown as Envelope<RolesViewData>;
    return {
      ok: true,
      exit_code: 0,
      data: {
        roles: roles.data as RolesData,
        profiles: profiles.data as ProfilesData,
        presets: presets.data as PresetsData,
        hub,
      },
      output: [],
      messages: [],
      command: roles.command,
      elapsed_ms: 0,
    };
  });

export default function RolesPage() {
  // live 单独读一次（合同第 2 节）：null 表示还没回来，证书格写「读取中」；卸载之后不写状态。
  // 读不读得出都不参与整页失败判定，也不等 loadRoles 的四个读。
  const [live, setLive] = useState<Envelope<QuizsLiveData> | null>(null);
  useEffect(() => {
    let on = true;
    getQuizsLive().then((env) => {
      if (on) setLive(env);
    });
    return () => {
      on = false;
    };
  }, []);
  return (
    <PageFrame<RolesViewData>
      title="角色与模型"
      description="四个角色各用哪个 CLI 与模型；方案可以一键切换"
      load={loadRoles}
      actions={(reload) => (
        <>
          <DisabledAction label="保存当前为方案…" />
          <NewProfileAction reload={reload} />
        </>
      )}
    >
      {(data, reload) => <RolesView data={data} onDiff={diffPresets} reload={reload} live={live} />}
    </PageFrame>
  );
}
