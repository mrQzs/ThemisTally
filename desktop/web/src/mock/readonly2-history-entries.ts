// 历史一条的夹具（示意）：42（两键差异）、41（本机文件，两个 64 位十六进制 sha256）、40（diff 为 null，note 疑似凭据）。
// 接本机服务后由 getHistoryEntry 直接读服务，本文件作废。
export interface HistoryKeyDiff {
  key: string;
  old: unknown;
  new: unknown;
}

export interface HistoryEntryData {
  number: number;
  resource: string;
  state: string | null;
  note: string | null;
  diff: HistoryKeyDiff[] | null;
  /** 本机文件记录才有：改动前后的 sha256。 */
  before_sha256?: string;
  after_sha256?: string;
}

const SHA_A = 'a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90';
const SHA_B = '0f1e2d3c4b5a69788796a5b4c3d2e1f00f1e2d3c4b5a69788796a5b4c3d2e1f0';

export const HISTORY_ENTRIES: Record<number, HistoryEntryData> = {
  42: {
    number: 42,
    resource: 'config',
    state: 'published',
    note: null,
    diff: [
      { key: 'active_preset', old: 'economy', new: 'default' },
      { key: 'roles.execution.profile', old: 'step-low', new: 'step-high' },
    ],
  },
  41: {
    number: 41,
    resource: 'local',
    state: 'published',
    note: '本机文件不存快照',
    diff: null,
    before_sha256: SHA_A,
    after_sha256: SHA_B,
  },
  40: {
    number: 40,
    resource: 'config',
    state: 'published',
    note: '（含疑似凭据，不显示）',
    diff: null,
  },
};
