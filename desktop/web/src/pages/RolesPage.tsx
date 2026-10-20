// 角色与模型页占位（合同第 9 条）：load=getRoles，说明「四个角色各用哪个 CLI 与模型；方案可以一键切换」（UI 文档 6.4 :558）。
import { PageFrame } from '../shell/PageFrame';
import { getRoles, type RolesData } from '../api';

const isRolesEmpty = (d: RolesData) => d.roles.length === 0;

export default function RolesPage() {
  return (
    <PageFrame<RolesData>
      title="角色与模型"
      description="四个角色各用哪个 CLI 与模型；方案可以一键切换"
      load={getRoles}
      isEmpty={isRolesEmpty}
    >
      {(data) => <p className="tt-page__read">夹具数据已读到：getRoles，{data.roles.length} 条。</p>}
    </PageFrame>
  );
}
