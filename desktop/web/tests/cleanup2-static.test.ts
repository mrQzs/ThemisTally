// 单一来源静态自测（T014 D01）：复制件、CopyNote 与三个图标在扫描范围里各只有一份定义；
// 六份重复文件已删除，且 src 与 tests 下没有文件再从它们引入。
// 扫描范围按合同：src/components、src/pages、src/shellpages、src/icons（src/showcase 有演示用的同类文字，天然在范围外）。
// 路径一律相对 desktop/web（vitest 的 cwd）。
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const web = process.cwd();
const read = (rel: string) => readFileSync(resolve(web, rel), 'utf8');

/** 收集若干目录（相对 desktop/web）下的 ts/tsx：{相对路径: 文本}。 */
function sourcesUnder(dirs: string[]): Record<string, string> {
  const out: Record<string, string> = {};
  const walk = (full: string, relDir: string) => {
    for (const name of readdirSync(full)) {
      const childRel = relDir ? `${relDir}/${name}` : name;
      const child = join(full, name);
      if (statSync(child).isDirectory()) walk(child, childRel);
      else if (/\.tsx?$/.test(name)) out[childRel] = readFileSync(child, 'utf8');
    }
  };
  for (const dir of dirs) walk(resolve(web, dir), dir);
  return out;
}
function stripComments(t: string): string {
  return t.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:'"`])\/\/[^\n]*/g, '$1');
}
/** 把 name 作为模块级导出函数/常量定义的文件（不含 export { … } from 的转出）。 */
function defsOf(files: Record<string, string>, name: string): string[] {
  return Object.keys(files).filter((rel) =>
    new RegExp(`export\\s+(?:async\\s+)?function\\s+${name}\\b|export\\s+(?:const|let|var)\\s+${name}\\b`)
      .test(stripComments(files[rel]))).sort();
}
/** 文本里出现某个字面量的文件。 */
function where(files: Record<string, string>, literal: string): string[] {
  return Object.keys(files).filter((rel) => files[rel].includes(literal)).sort();
}

const SRC_DIRS = ['src/components', 'src/pages', 'src/shellpages', 'src/icons'];
const SRC = sourcesUnder(SRC_DIRS);
const ALL = { ...sourcesUnder(['src']), ...sourcesUnder(['tests']) };
const COPY_TEXT = 'src/components/copyText.ts';
const COPY_NOTE = 'src/components/CopyNote.tsx';
const RO1_COPY_NOTE = 'src/pages/readonly1/common-CopyNote.tsx';
const ICONS = 'src/icons/index.tsx';
const RESULT_STRINGS = ['这个环境没有剪贴板接口', '已复制', '复制失败'];
// 合同 Scope allowed_deleted_files：六份重复件。
const DELETED = [
  'src/pages/tasks/tasks-copy.ts',
  'src/pages/tasks/tasks-icons.tsx',
  'src/pages/tasks/common-CopyNote.tsx',
  'src/shellpages/copy.ts',
  'src/shellpages/icons.tsx',
  'src/pages/readonly2/common-icons.tsx',
];
const DELETED_STEMS = DELETED.map((rel) => rel.replace(/\.tsx?$/, ''));

describe('复制件只有一份', () => {
  it('copyText 与 COPY_RESULT_TEXT 各只有一处导出定义，都在 components/copyText.ts', () => {
    for (const name of ['copyText', 'COPY_RESULT_TEXT']) {
      expect(defsOf(SRC, name), name).toEqual([COPY_TEXT]);
    }
  });

  it('三条结果文字只出现在 components/copyText.ts', () => {
    for (const s of RESULT_STRINGS) expect(where(SRC, s), s).toEqual([COPY_TEXT]);
  });
});

describe('CopyNote 只有一份', () => {
  it('CopyNote 组件定义只在 components/CopyNote.tsx', () => {
    expect(defsOf(SRC, 'CopyNote')).toEqual([COPY_NOTE]);
  });

  it('readonly1/common-CopyNote.tsx 只转出，不再自己定义组件与私有文字表', () => {
    expect(existsSync(resolve(web, RO1_COPY_NOTE))).toBe(true);
    const code = stripComments(ALL[RO1_COPY_NOTE]);
    expect(code).not.toMatch(/export\s+(?:function|const)\s+CopyNote\b/);
    expect(code).not.toMatch(/export\s+(?:interface|type)\s+CopyNoteProps\b/);
    for (const s of RESULT_STRINGS) expect(ALL[RO1_COPY_NOTE].includes(s), s).toBe(false);
  });
});

describe('三个图标只有一份', () => {
  it('ArrowRightIcon、FileTextIcon、ExternalLinkIcon 各只有一处 export const，都在 src/icons/index.tsx', () => {
    for (const name of ['ArrowRightIcon', 'FileTextIcon', 'ExternalLinkIcon']) {
      expect(defsOf(SRC, name), name).toEqual([ICONS]);
    }
  });
});

describe('六份重复件已删除且无人引入', () => {
  it('六个文件都不存在', () => {
    for (const rel of DELETED) expect(existsSync(resolve(web, rel)), `${rel} 应已删除`).toBe(false);
  });

  it('src 与 tests 下没有文件再从它们引入', () => {
    const bad: string[] = [];
    for (const rel of Object.keys(ALL)) {
      const code = stripComments(ALL[rel]);
      const dir = rel.split('/').slice(0, -1).join('/');
      for (const m of code.matchAll(/import\s+(?:type\s+)?\{([^}]*)\}\s+from\s+['"](\.[^'"]+)['"]/g)) {
        const parts = [...dir.split('/'), ...m[2].split('/')];
        const stack: string[] = [];
        for (const part of parts) {
          if (part === '.' || part === '') continue;
          if (part === '..') stack.pop();
          else stack.push(part);
        }
        if (DELETED_STEMS.includes(stack.join('/'))) bad.push(`${rel} → ${m[2]}`);
      }
    }
    expect(bad).toEqual([]);
  });
});
