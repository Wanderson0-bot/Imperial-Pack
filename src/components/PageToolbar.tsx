import type { ReactNode } from 'react';

type PageToolbarProps = {
  left?: ReactNode;
  right?: ReactNode;
};

export function PageToolbar({ left, right }: PageToolbarProps) {
  return (
    <div className="workspace-toolbar">
      <div className="workspace-toolbar__left">{left}</div>
      <div className="workspace-toolbar__right">{right}</div>
    </div>
  );
}
