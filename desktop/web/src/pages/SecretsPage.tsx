// 凭据页（合同第 9 条 / D01）：load=listSecrets，说明「这里只显示每个环境变量在哪一层找到，从不显示值」（UI 文档 10.3），
// 刷新钮叫「重新检查」，空态「还没有要检查的凭据变量」。
import { PageFrame } from '../shell/PageFrame';
import { listSecrets, type SecretsData } from '../api';
import { SecretsView } from './readonly2/secrets-SecretsView';

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
      {(data) => <SecretsView data={data} />}
    </PageFrame>
  );
}
