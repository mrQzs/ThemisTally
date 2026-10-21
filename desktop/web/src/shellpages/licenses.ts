// 开源许可清单数据（src/shellpages/licenses.ts）：只列 Lucide 与 Sarasa Gothic（K10），
// 只写项目名、版本、许可、版权与随包路径；只当文字、不做链接、不写字体文件名（G3）。
// React、ReactDOM 不补进 THIRD_PARTY_NOTICES（K10）。

export interface LicenseEntry {
  name: string;
  version: string;
  license: string;
  copyright: string;
  path: string;
}

export const LICENSES: readonly LicenseEntry[] = [
  {
    name: 'Lucide',
    version: '1.59.0',
    license: 'ISC',
    copyright: 'Copyright (c) 2020 Lucide Contributors（派生自 Feather 的图标另附 MIT 许可）',
    path: 'licenses/lucide-1.59.0-LICENSE.txt',
  },
  {
    name: 'Sarasa Gothic（等距更纱黑体 SC）',
    version: '0.36.0',
    license: 'SIL OFL 1.1',
    copyright:
      'Copyright (c) 2015 Renzhi Li\nCopyright (c) 2015-2021 Tomona Nanase\nCopyright (c) 2019-2021 Belleve Invis\nCopyright (c) 2020 Xuerdong Yi',
    path: 'licenses/OFL.txt',
  },
];
