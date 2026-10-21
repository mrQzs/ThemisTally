// 插件详情的夹具（示意）：三个插件与 plugins.json 一致；docs-checks 的 permissions 含 fs.read、fs.write，
// 缺 fs.write；资源两行一致（manifest.json、checks/headings.py）；锁有 generation 与 64 位十六进制 lock_sha256。
// 接本机服务后由 getPlugin 直接读服务，本文件作废。
export interface PluginResource {
  path: string;
  id: string;
  sha256: string;
  status: string;
  detail: string;
}

export interface PluginShowData {
  plugin_id: string;
  lock_status: string;
  resource_status: string;
  problems: string[];
  version: string;
  api_version: string;
  capabilities: string[];
  permissions: string[];
  platforms: string[];
  depends_on: string[];
  conflicts: string[];
  checks: string[];
  lock: { generation: number; lock_sha256: string };
  resources: PluginResource[];
  config: { enabled: string | null; allowed_permissions: string[]; missing_permissions: string[] };
}

const LOCK_A = '4d3c2b1a09f8e7d6c5b4a39281706f5e4d3c2b1a09f8e7d6c5b4a39281706f5e';
const LOCK_B = '9e8d7c6b5a4938271605f4e3d2c1b0a99e8d7c6b5a4938271605f4e3d2c1b0a9';
const LOCK_C = '1c2b3a49586776859403a1b2c3d4e5f61c2b3a49586776859403a1b2c3d4e5f6';
const RES_A = '5a6b7c8d9e0f1a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b';
const RES_B = '6b7c8d9e0f1a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c';
const RES_C = '7c8d9e0f1a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d';
const RES_D = '8d9e0f1a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e';

function resources(manifest: string, extra: string): PluginResource[] {
  return [
    { path: 'manifest.json', id: 'manifest', sha256: manifest, status: '一致', detail: '' },
    { path: 'checks/headings.py', id: 'headings', sha256: extra, status: '一致', detail: '' },
  ];
}

export const PLUGIN_SHOWS: Record<string, PluginShowData> = {
  decisions: {
    plugin_id: 'decisions',
    lock_status: '一致',
    resource_status: '一致',
    problems: [],
    version: '1.0.0',
    api_version: '1',
    capabilities: ['review'],
    permissions: ['fs.read'],
    platforms: ['windows', 'linux'],
    depends_on: [],
    conflicts: [],
    checks: ['核对 manifest 的字段是否齐全'],
    lock: { generation: 3, lock_sha256: LOCK_A },
    resources: resources(RES_A, RES_B),
    config: { enabled: '启用', allowed_permissions: ['fs.read'], missing_permissions: [] },
  },
  'code-change': {
    plugin_id: 'code-change',
    lock_status: '一致',
    resource_status: '一致',
    problems: [],
    version: '1.0.0',
    api_version: '1',
    capabilities: ['edit'],
    permissions: ['fs.read', 'fs.write'],
    platforms: ['windows'],
    depends_on: [],
    conflicts: [],
    checks: ['核对改动是否越出合同范围'],
    lock: { generation: 5, lock_sha256: LOCK_B },
    resources: resources(RES_C, RES_D),
    config: { enabled: '停用', allowed_permissions: ['fs.read', 'fs.write'], missing_permissions: [] },
  },
  'docs-checks': {
    plugin_id: 'docs-checks',
    lock_status: '漂移',
    resource_status: '一致',
    problems: [],
    version: '1.0.0',
    api_version: '1',
    capabilities: ['docs', 'headings'],
    permissions: ['fs.read', 'fs.write'],
    platforms: ['windows', 'linux'],
    depends_on: [],
    conflicts: [],
    checks: ['核对文档标题层级是否连续'],
    lock: { generation: 7, lock_sha256: LOCK_C },
    resources: resources(RES_A, RES_B),
    config: { enabled: null, allowed_permissions: ['fs.read'], missing_permissions: ['fs.write'] },
  },
};
