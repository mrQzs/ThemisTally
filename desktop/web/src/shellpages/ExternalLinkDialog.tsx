// 外部链接确认对话框（src/shellpages/ExternalLinkDialog.tsx）：标题「在系统浏览器中打开？」、正文完整网址、说明。
// 底栏 [取消]（secondary）与 [打开]（primary）；Esc、关闭钮、[取消] 都不调 openExternal，[打开] 调一次并关闭。
import { Button, Dialog } from '../components';

export interface ExternalLinkDialogProps {
  open: boolean;
  url: string;
  onClose: () => void;
  onConfirm: () => void;
}

export function ExternalLinkDialog({ open, url, onClose, onConfirm }: ExternalLinkDialogProps) {
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="在系统浏览器中打开？"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            取消
          </Button>
          <Button variant="primary" onClick={onConfirm}>
            打开
          </Button>
        </>
      }
    >
      <code className="tt-st__url">{url}</code>
      <span className="tt-st__url-cap">只允许 http 与 https；由外壳交给系统浏览器打开。</span>
    </Dialog>
  );
}
