// 外壳设置页视图（src/shellpages/SettingsView.tsx）：五组——仓库、运行环境、规划端用量、外观、关于。
// 根元素 data-page=settings，不渲染 h1、不写 data-page-state（h1 与 data-page-state 由 PageFrame 出）。
// 收 PageFrame 的 data 作初值放本地状态；每次操作之后只用返回的 ShellState 更新（不做乐观更新）；
// PageFrame 刷新带来新 data 时换掉本地状态。每个按钮调用期间是加载态；被拒时在本组顶部显示 danger Banner。
import { useEffect, useState } from 'react';
import { Banner, Button, KeyValueList, SegmentedControl, Tag } from '../components';
import { Logo } from '../shell/Logo';
import { DisabledAction } from '../shell/DisabledAction';
import { FolderPlusIcon } from '../icons/frame';
import type { ShellState, ThemisShell } from './themisShell';
import type { ThemePref } from '../shell/theme';
import { useThemePref } from './themePref';
import { openedTitle, relTime } from './format';
import { LicensesDialog } from './LicensesDialog';
import { ExternalLinkDialog } from './ExternalLinkDialog';
import { FileTextIcon, ExternalLinkIcon } from '../icons';
import './settings.css';

export interface SettingsViewProps {
  data: ShellState;
  shell: ThemisShell;
}

function reasonOf(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

export function SettingsView({ data, shell }: SettingsViewProps) {
  const [state, setState] = useState<ShellState>(data);
  const [banner, setBanner] = useState<{ group: string; text: string } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [licensesOpen, setLicensesOpen] = useState(false);
  const [extOpen, setExtOpen] = useState(false);
  const { theme, setTheme } = useThemePref();

  // PageFrame 刷新带来新 data 时换掉本地状态。
  useEffect(() => {
    setState(data);
  }, [data]);

  const setBannerFor = (group: string, text: string) => setBanner({ group, text });
  const clearBanner = (group: string) => setBanner((b) => (b && b.group === group ? null : b));

  const run = async (key: string, fn: () => Promise<void>) => {
    setBusy(key);
    try {
      await fn();
    } finally {
      setBusy(null);
    }
  };

  // 仓库
  const onAddRepo = () =>
    run('add-repo', async () => {
      const r = await shell.pickRepo();
      if (r.kind === 'saved') {
        setState(r.state);
        clearBanner('repos');
      } else if (r.kind === 'rejected') {
        setBannerFor(
          'repos',
          r.problem === 'no-agent'
            ? `这个仓库还没有接入 Themis Tally。在终端里运行 python <ThemisTally>/scripts/kit_install.py install ${r.path} 接入。`
            : '这个文件夹不是 Git 仓库。',
        );
      }
    });
  const onRemoveRepo = (id: string) =>
    run(`remove-repo:${id}`, async () => {
      try {
        setState(await shell.saveSettings({ removeRepo: id }));
        clearBanner('repos');
      } catch (e) {
        setBannerFor('repos', `没能保存：${reasonOf(e)}`);
      }
    });

  // 运行环境
  const onChangePython = () =>
    run('change-python', async () => {
      const r = await shell.pickPython();
      if (r.kind === 'saved') {
        setState(r.state);
        clearBanner('runtime');
      } else if (r.kind === 'rejected') {
        setBannerFor('runtime', `没能保存：所选的 python.exe 不能用：${r.path}`);
      }
    });
  const onResetPython = () =>
    run('reset-python', async () => {
      try {
        setState(await shell.saveSettings({ resetPython: true }));
        clearBanner('runtime');
      } catch (e) {
        setBannerFor('runtime', `没能保存：${reasonOf(e)}`);
      }
    });
  const onChangeKit = () =>
    run('change-kit', async () => {
      const r = await shell.pickKit();
      if (r.kind === 'saved') {
        setState(r.state);
        clearBanner('runtime');
      } else if (r.kind === 'rejected') {
        setBannerFor('runtime', `没能保存：所选目录里的 kit 不能用：${r.path}`);
      }
    });
  const onResetKit = () =>
    run('reset-kit', async () => {
      try {
        setState(await shell.saveSettings({ resetKit: true }));
        clearBanner('runtime');
      } catch (e) {
        setBannerFor('runtime', `没能保存：${reasonOf(e)}`);
      }
    });

  // 规划端用量
  const onChooseDir = () =>
    run('choose-dir', async () => {
      const r = await shell.pickTranscriptDir();
      if (r.kind === 'saved') {
        setState(r.state);
        clearBanner('usage');
      }
    });
  const onRemoveDir = (id: string) =>
    run(`remove-dir:${id}`, async () => {
      try {
        setState(await shell.saveSettings({ removeTranscriptDir: id }));
        clearBanner('usage');
      } catch (e) {
        setBannerFor('usage', `没能保存：${reasonOf(e)}`);
      }
    });

  // 外观
  const onTheme = (value: string) => {
    setTheme(value as ThemePref);
    shell
      .saveSettings({ theme: value as ShellState['settings']['theme'] })
      .then(() => clearBanner('appearance'))
      .catch((e) => setBannerFor('appearance', `主题已切换，但没能保存：${reasonOf(e)}`));
  };
  const onDensity = (value: string) =>
    run('density', async () => {
      try {
        setState(await shell.saveSettings({ density: value as ShellState['settings']['density'] }));
        clearBanner('appearance');
      } catch (e) {
        setBannerFor('appearance', `没能保存：${reasonOf(e)}`);
      }
    });

  // 关于
  const homepage = state.app.homepage;
  const homepageOk = /^https?:\/\//.test(homepage);
  const onConfirmExt = async () => {
    try {
      await shell.openExternal(homepage);
    } catch {
      // 只允许 http 与 https；非 http(s) 不显示 [项目主页]，这里不会到。
    }
    setExtOpen(false);
  };

  const { settings, currentRepoCheck, python, kit, app } = state;
  const currentRepo = settings.currentRepo;
  const now = Date.now();

  const pythonCaption =
    python.status === 'missing'
      ? '找不到 Python 3.10 及以上'
      : `${python.source === 'custom' ? '手动指定' : '自动检测'} · ${python.version}`;
  const kitCaption =
    kit.status === 'missing'
      ? '找不到 Themis Tally 的 kit。'
      : `${kit.source === 'external' ? '外部目录' : '仓库里装好的'} · ${kit.version}`;

  const GroupBanner = ({ group }: { group: string }) =>
    banner && banner.group === group ? <Banner tone="danger">{banner.text}</Banner> : null;

  return (
    <div className="tt-st" data-page="settings">
      {/* 仓库 */}
      <section className="tt-st__group" data-settings-group="repos">
        <GroupBanner group="repos" />
        <div className="tt-st__group-head">
          <h2 className="tt-st__h2">仓库</h2>
          <Button variant="secondary" size="sm" loading={busy === 'add-repo'} onClick={onAddRepo}>
            <FolderPlusIcon width={14} height={14} />
            添加仓库…
          </Button>
        </div>
        <div className="tt-st__scroll">
          <table className="tt-st__table">
            <thead>
              <tr>
                <th scope="col">名称</th>
                <th scope="col">路径</th>
                <th scope="col">上次打开</th>
                <th scope="col" className="tt-st__th-act">
                  操作
                </th>
              </tr>
            </thead>
            <tbody>
              {settings.repos.length === 0 ? (
                <tr>
                  <td colSpan={4} className="tt-st__empty">
                    还没有添加仓库
                  </td>
                </tr>
              ) : (
                settings.repos.map((repo) => (
                  <tr key={repo.id} data-repo-id={repo.id}>
                    <td>
                      <span className="tt-st__mono">{repo.name}</span>
                      {repo.id === currentRepo && (
                        <Tag tone="brand" className="tt-st__cur">
                          当前
                        </Tag>
                      )}
                    </td>
                    <td className="tt-st__mono tt-st__path">{repo.path}</td>
                    <td
                      className="tt-st__opened"
                      title={repo.id === currentRepo || !repo.lastOpened ? undefined : openedTitle(repo.lastOpened)}
                    >
                      {repo.id === currentRepo ? '现在' : relTime(repo.lastOpened, now)}
                    </td>
                    <td className="tt-st__act">
                      {repo.id === currentRepo ? (
                        <DisabledAction label="从列表移除" reason="不能移除当前打开的仓库" variant="ghost" size="sm" />
                      ) : (
                        <Button
                          variant="ghost"
                          size="sm"
                          loading={busy === `remove-repo:${repo.id}`}
                          onClick={() => onRemoveRepo(repo.id)}
                        >
                          从列表移除
                        </Button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        <p className="tt-st__group-note">“从列表移除”只从应用里移除，不动仓库。</p>
      </section>

      {/* 运行环境 */}
      <section className="tt-st__group" data-settings-group="runtime">
        <GroupBanner group="runtime" />
        <h2 className="tt-st__h2">运行环境</h2>
        <div className="tt-st__row tt-stack-narrow">
          <span className="tt-st__label">Python</span>
          <div className="tt-st__value">
            <code className="tt-st__mono tt-st__path">{python.path || '—'}</code>
            <span className={`tt-st__caption${python.status === 'missing' ? ' tt-st__caption--bad' : ''}`}>{pythonCaption}</span>
          </div>
          <Button variant="secondary" loading={busy === 'change-python'} onClick={onChangePython}>
            更改…
          </Button>
          {python.source === 'custom' && (
            <Button variant="secondary" loading={busy === 'reset-python'} onClick={onResetPython}>
              恢复自动检测
            </Button>
          )}
        </div>
        <div className="tt-st__row tt-stack-narrow">
          <span className="tt-st__label">kit 位置</span>
          <div className="tt-st__value">
            <code className="tt-st__mono tt-st__path">{kit.path || '—'}</code>
            <span className={`tt-st__caption${kit.status === 'missing' ? ' tt-st__caption--bad' : ''}`}>{kitCaption}</span>
          </div>
          <Button variant="secondary" loading={busy === 'change-kit'} onClick={onChangeKit}>
            更改…
          </Button>
          {kit.source === 'external' && (
            <Button variant="secondary" loading={busy === 'reset-kit'} onClick={onResetKit}>
              恢复自动检测
            </Button>
          )}
        </div>
        <div className="tt-st__row tt-stack-narrow">
          <span className="tt-st__label">版本信息</span>
          <KeyValueList
            items={[
              { label: '桌面端', value: app.version, mono: true },
              { label: 'kit', value: kit.status === 'ok' ? kit.version : '—', mono: true },
              { label: 'Python', value: python.status === 'ok' ? python.version : '—', mono: true },
            ]}
          />
        </div>
        <p className="tt-st__group-note">改了 Python、kit 或会话记录目录，保存后外壳会重启本机服务。</p>
      </section>

      {/* 规划端用量 */}
      <section className="tt-st__group" data-settings-group="usage">
        <GroupBanner group="usage" />
        <h2 className="tt-st__h2">规划端用量</h2>
        <div className="tt-st__row tt-stack-narrow">
          <span className="tt-st__label">会话记录目录</span>
          <div className="tt-st__dirs">
            {settings.transcriptDirs.length === 0 ? (
              <span className="tt-st__unset">未设置（可选）</span>
            ) : (
              settings.transcriptDirs.map((dir) => (
                <div key={dir.id} className="tt-st__dir">
                  <code className="tt-st__mono tt-st__path">{dir.path}</code>
                  <Button variant="ghost" size="sm" loading={busy === `remove-dir:${dir.id}`} onClick={() => onRemoveDir(dir.id)}>
                    移除
                  </Button>
                </div>
              ))
            )}
          </div>
          <Button variant="secondary" loading={busy === 'choose-dir'} onClick={onChooseDir}>
            选择目录…
          </Button>
        </div>
        <p className="tt-st__group-note">
          只读用量字段，不读对话内容。设置后在“日志与用量 › 用量”里按模型列出，分主线与子代理。保存后重启服务生效。
        </p>
      </section>

      {/* 外观 */}
      <section className="tt-st__group" data-settings-group="appearance">
        <GroupBanner group="appearance" />
        <h2 className="tt-st__h2">外观</h2>
        <div className="tt-st__row">
          <span className="tt-st__label">主题</span>
          <SegmentedControl
            aria-label="主题"
            value={theme}
            onChange={onTheme}
            options={[
              { value: 'system', label: '跟随系统' },
              { value: 'light', label: '亮' },
              { value: 'dark', label: '暗' },
            ]}
          />
        </div>
        <div className="tt-st__row">
          <span className="tt-st__label">密度</span>
          <SegmentedControl
            aria-label="密度"
            value={settings.density}
            onChange={onDensity}
            options={[
              { value: 'standard', label: '标准' },
              { value: 'compact', label: '紧凑' },
            ]}
          />
          <span className="tt-st__caption">紧凑：表格行高 32</span>
        </div>
      </section>

      {/* 关于 */}
      <section className="tt-st__group" data-settings-group="about">
        <h2 className="tt-st__h2">关于</h2>
        <div className="tt-st__about">
          <span className="tt-st__about-logo" aria-hidden="true">
            <Logo />
          </span>
          <div className="tt-st__about-text">
            <span className="tt-st__about-name">Themis Tally · 参验</span>
            <span className="tt-st__about-ver">
              版本 <span className="tt-st__mono">{app.version}</span>
            </span>
          </div>
        </div>
        <div className="tt-st__about-actions">
          <Button variant="secondary" onClick={() => setLicensesOpen(true)}>
            <FileTextIcon width={16} height={16} />
            开源许可清单
          </Button>
          {homepageOk ? (
            <Button variant="secondary" onClick={() => setExtOpen(true)}>
              <ExternalLinkIcon width={16} height={16} />
              项目主页
            </Button>
          ) : (
            <span className="tt-st__caption">{homepage}</span>
          )}
        </div>
      </section>

      <LicensesDialog open={licensesOpen} onClose={() => setLicensesOpen(false)} />
      <ExternalLinkDialog open={extOpen} url={homepage} onClose={() => setExtOpen(false)} onConfirm={onConfirmExt} />
    </div>
  );
}
