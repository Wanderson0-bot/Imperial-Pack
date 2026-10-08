import type { ReactNode } from 'react';

type EmptyStateProps = { title: string; description?: string; action?: ReactNode };
export function EmptyState({ title, description, action }: EmptyStateProps) {
  return <div className="empty-state"><div className="empty-state__mark" aria-hidden="true">—</div><div className="empty-state__content"><h3>{title}</h3>{description ? <p>{description}</p> : null}</div>{action ? <div>{action}</div> : null}</div>;
}
