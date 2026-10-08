import type { ReactNode } from 'react';

type TopbarProps = {
  title?: string;
  subtitle?: string;
  actions?: ReactNode;
};

export function Topbar({ title, subtitle, actions }: TopbarProps) {
  return (
    <header className="topbar-shell">
      <div className="topbar-shell__context">
        {subtitle ? <span className="topbar-shell__subtitle">{subtitle}</span> : null}
        {title ? <strong className="topbar-shell__title">{title}</strong> : null}
      </div>
      {actions ? <div className="topbar-shell__actions">{actions}</div> : null}
    </header>
  );
}
