import { useEffect, useState } from 'react';
import { Button, Tag, StatusTag, Card, Banner } from './components';
import { ATTEMPT_STATES } from './domain/attemptStates';
import './App.css';

type ThemePref = 'dark' | 'light' | 'system';

const STATE_CODES = Object.keys(ATTEMPT_STATES);
const TAG_TONES = ['neutral', 'info', 'attention', 'success', 'warning', 'danger', 'escalate', 'brand'] as const;

function applyTheme(pref: ThemePref) {
  const root = document.documentElement;
  if (pref === 'dark') {
    root.removeAttribute('data-theme');
  } else {
    root.setAttribute('data-theme', pref);
  }
}

function ThemeButton({ pref, current, onSelect }: { pref: ThemePref; current: ThemePref; onSelect: (p: ThemePref) => void }) {
  const label = pref === 'dark' ? '暗' : pref === 'light' ? '亮' : '跟随系统';
  return (
    <Button
      variant={current === pref ? 'primary' : 'secondary'}
      size="sm"
      aria-pressed={current === pref}
      onClick={() => onSelect(pref)}
    >
      {label}
    </Button>
  );
}

export default function App() {
  const [theme, setTheme] = useState<ThemePref>('dark');
  const [bannerOpen, setBannerOpen] = useState(true);

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  return (
    <div className="tt-app tt-content showcase">
      <header className="showcase__head">
        <h1 className="showcase__title">Themis Tally · 组件陈列</h1>
        <div className="showcase__theme" role="group" aria-label="切换主题">
          <ThemeButton pref="dark" current={theme} onSelect={setTheme} />
          <ThemeButton pref="light" current={theme} onSelect={setTheme} />
          <ThemeButton pref="system" current={theme} onSelect={setTheme} />
        </div>
      </header>

      <section className="showcase__section">
        <h2 className="showcase__h2">Button 按钮</h2>
        <div className="showcase__row">
          <span className="showcase__label">变体</span>
          <Button variant="primary">主按钮</Button>
          <Button variant="secondary">次按钮</Button>
          <Button variant="ghost">幽灵按钮</Button>
          <Button variant="danger">危险按钮</Button>
        </div>
        <div className="showcase__row">
          <span className="showcase__label">尺寸</span>
          <Button size="sm" variant="secondary">小 28</Button>
          <Button size="md" variant="secondary">中 32</Button>
          <Button size="lg" variant="secondary">大 36</Button>
        </div>
        <div className="showcase__row">
          <span className="showcase__label">加载 / 禁用</span>
          <Button variant="primary" loading loadingText="正在切换…">切换</Button>
          <Button variant="secondary" disabled>禁用</Button>
        </div>
      </section>

      <section className="showcase__section">
        <h2 className="showcase__h2">Tag 标签</h2>
        <div className="showcase__row">
          <span className="showcase__label">色调</span>
          {TAG_TONES.map((tone) => (
            <Tag key={tone} tone={tone}>{tone}</Tag>
          ))}
        </div>
        <div className="showcase__row">
          <span className="showcase__label">等宽</span>
          <Tag tone="brand" mono>active_preset</Tag>
          <Tag tone="info" mono>agent:planning_review</Tag>
          <Tag tone="warning" mono>undeclared</Tag>
        </div>
      </section>

      <section className="showcase__section">
        <h2 className="showcase__h2">StatusTag 状态标签</h2>
        <div className="showcase__row">
          <span className="showcase__label">17 个状态</span>
          <div className="showcase__wrap">
            {STATE_CODES.map((code) => (
              <StatusTag key={code} state={code} />
            ))}
          </div>
        </div>
        <div className="showcase__row">
          <span className="showcase__label">小号 / 未知</span>
          <StatusTag state="PASS" size="sm" />
          <StatusTag state="RUNNING" size="sm" />
          <StatusTag state="FUTURE_STATE" />
          <StatusTag state="WEIRD_CODE" />
        </div>
      </section>

      <section className="showcase__section">
        <h2 className="showcase__h2">Card 卡片</h2>
        <div className="showcase__cards">
          <Card
            title="卡片标题"
            actions={<Button variant="ghost" size="sm">卡头操作</Button>}
          >
            <p className="showcase__muted">surface-1 底、border 边、圆角 lg 8、内边距 16。</p>
          </Card>
          <Card title="仅标题">
            <p className="showcase__muted">没有右侧操作的卡片。</p>
          </Card>
        </div>
      </section>

      <section className="showcase__section">
        <h2 className="showcase__h2">Banner 提示条</h2>
        <div className="showcase__stack">
          {bannerOpen && (
            <Banner tone="info" onClose={() => setBannerOpen(false)}>
              info：只有 info 可以关掉。
            </Banner>
          )}
          <Banner tone="warning">历史里有 2 行读不出来。</Banner>
          <Banner tone="danger">与本机服务的连接断开。</Banner>
          {!bannerOpen && (
            <Button variant="ghost" size="sm" onClick={() => setBannerOpen(true)}>
              重新显示 info 提示条
            </Button>
          )}
        </div>
      </section>
    </div>
  );
}
