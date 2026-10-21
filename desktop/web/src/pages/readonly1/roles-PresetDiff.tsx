// 方案差异面板（合同第 5 节）：头「<active> 与 <name> 的差异 · 」接等宽命令；读取中/出错/有数据三态；
// same 真写「相同」，same 假写 角色名、− 旧绑定、+ 新绑定（减号 U+2212）；角色多于差异行数时末行「其余 M 个角色 相同」。
import type { PresetDiffData } from '../../api';
import { ArrowRightIcon } from '../../icons';
import { bindingText, roleName } from './roles-logic';

export type PresetDiffState =
  | { status: 'loading' }
  | { status: 'error'; command: string; exit_code: number; messages: string[] }
  | { status: 'data'; data: PresetDiffData };

export interface PresetDiffProps {
  id: string;
  active: string;
  name: string;
  state: PresetDiffState | null;
  totalRoles: number;
}

export function PresetDiff({ id, active, name, state, totalRoles }: PresetDiffProps) {
  const shown = state && state.status === 'data' ? state.data.roles.length : 0;
  return (
    <div className="rl-diff" id={id}>
      <div className="rl-diff__head">
        <span className="rl-diff__title">
          {active} 与 {name} 的差异 ·{' '}
        </span>
        <code className="rl-diff__cmd">config preset diff {active} {name}</code>
      </div>
      {state == null || state.status === 'loading' ? (
        <p className="rl-diff__status">正在读取…</p>
      ) : state.status === 'error' ? (
        <div className="rl-diff__error">
          <p className="rl-diff__errtext">
            没能读到差异：命令 {state.command} 返回退出码 {state.exit_code}。
          </p>
          <pre className="rl-diff__msg">{state.messages.join('\n')}</pre>
        </div>
      ) : (
        <div className="rl-diff__rows">
          {state.data.roles.map((entry) => (
            <div className="rl-diff__row" key={entry.role}>
              <span className="rl-diff__role">{roleName(entry.role)}</span>
              {entry.same ? (
                <span className="rl-diff__same">相同</span>
              ) : (
                <>
                  <span className="rl-diff__val rl-diff__del">
                    {'\u2212'}
                    {bindingText(entry.a)}
                  </span>
                  <ArrowRightIcon width={16} height={16} className="rl-diff__arrow" />
                  <span className="rl-diff__val rl-diff__add">+{bindingText(entry.b)}</span>
                </>
              )}
            </div>
          ))}
          {shown < totalRoles && <p className="rl-diff__rest">其余 {totalRoles - shown} 个角色 相同</p>}
        </div>
      )}
    </div>
  );
}
