import type { ReactNode } from 'react';

type DrawerProps = {
  isOpen?: boolean;
  title?: string;
  children: ReactNode;
};

export function Drawer({ isOpen = false, title, children }: DrawerProps) {
  if (!isOpen) return null;

  return (
    <div className="drawer" aria-label={title ?? 'Detalhes'}>
      {title ? <header className="drawer__header"><strong>{title}</strong></header> : null}
      <div className="drawer__body">{children}</div>
    </div>
  );
}
