import type { ReactNode } from 'react';

type DetailPanelProps = {
  title?: string;
  children: ReactNode;
  actions?: ReactNode;
};

export function DetailPanel({ title, children, actions }: DetailPanelProps) {
  return (
    <aside className="workspace-detail">
      {(title || actions) ? (
        <header className="workspace-detail__header">
          {title ? <strong>{title}</strong> : null}
          {actions ? <div>{actions}</div> : null}
        </header>
      ) : null}
      <div className="workspace-detail__body">{children}</div>
    </aside>
  );
}
