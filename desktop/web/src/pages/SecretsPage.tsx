// 凭据页占位（合同第 9 条）：load=listSecrets，说明「这里只显示每个环境变量在哪一层找到，从不显示值」（10.3），
// 刷新钮叫「重新检查」，空态「还没有要检查的凭据变量」。
import { PageFrame } from '../shell/PageFrame';
import { listSecrets, type SecretsData } from '../api';

const isSecretsEmpty = (d: SecretsData) => d.secrets.length === 0;

export default function SecretsPage() {
  return (
    <PageFrame<SecretsData>
      title="凭据"
      description="这里只显示每个环境变量在哪一层找到，从不显示值"
      refreshLabel="重新检查"
      load={listSecrets}
      isEmpty={isSecretsEmpty}
      empty={{ title: '还没有要检查的凭据变量' }}
    >
      {(data) => <p className="tt-page__read">夹具数据已读到：listSecrets，{data.secrets.length} 条。</p>}
    </PageFrame>
  );
}
