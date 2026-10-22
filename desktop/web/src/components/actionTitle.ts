// 动作的中文说明（共用件）：T013 把只读页一、二的两份动作表并成这一份，表只在这里维护。
// 13 条与 UI 文档 10.4 逐字相同；表外动作不带 title（返回 null）。
export const ACTION_TITLES: Record<string, string> = {
  'config.set': '设置配置键',
  'config.unset': '删除配置键',
  'config.rollback': '回滚配置',
  'preset.use': '切换方案',
  'preset.save': '保存方案',
  'preset.remove': '删除方案',
  'role.set': '修改角色绑定',
  'profile.add': '新建 profile',
  'profile.edit': '修改 profile',
  'profile.remove': '删除 profile',
  'runtime.add': '登记 runtime',
  'runtime.remove': '删除 runtime',
  external: '检测到界面与命令之外的改动',
};

/** 动作的中文说明（title）；表外动作返回 null。 */
export function actionTitle(action: string): string | null {
  return Object.prototype.hasOwnProperty.call(ACTION_TITLES, action) ? ACTION_TITLES[action] : null;
}
