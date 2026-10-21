// 开源许可清单对话框（src/shellpages/LicensesDialog.tsx）：逐项写名称、版本、许可、版权与许可原文的随包路径。
// 只当文字，不做链接，不写字体文件名。
import { Dialog } from '../components';
import { LICENSES } from './licenses';

export interface LicensesDialogProps {
  open: boolean;
  onClose: () => void;
}

export function LicensesDialog({ open, onClose }: LicensesDialogProps) {
  return (
    <Dialog open={open} onClose={onClose} title="开源许可清单">
      <div className="tt-st__lic">
        {LICENSES.map((entry) => (
          <div key={entry.name} className="tt-st__lic-item">
            <div className="tt-st__lic-head">
              <span className="tt-st__lic-name">{entry.name}</span>
              <span className="tt-st__lic-ver">{entry.version}</span>
              <span className="tt-st__lic-lic">{entry.license}</span>
            </div>
            <div className="tt-st__lic-copy">
              {entry.copyright.split('\n').map((line, i) => (
                <span key={i}>{line}</span>
              ))}
            </div>
            <div className="tt-st__lic-path">{entry.path}</div>
          </div>
        ))}
      </div>
    </Dialog>
  );
}
