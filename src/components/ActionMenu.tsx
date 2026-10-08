import type { ReactNode } from 'react';
type ActionMenuProps = { label?: string; children: ReactNode };
export function ActionMenu({ label = 'A\u00e7\u00f5es', children }: ActionMenuProps) {
  return <div className="action-menu" aria-label={label}><button type="button" className="action-menu__trigger" aria-haspopup="true">{label}</button><div className="action-menu__content">{children}</div></div>;
}

