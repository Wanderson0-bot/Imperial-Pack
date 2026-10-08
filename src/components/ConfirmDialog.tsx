import type { ReactNode } from 'react';

type ConfirmDialogProps = {
  title: string;
  description?: string;
  actions?: ReactNode;
};

export function ConfirmDialog({ title, description, actions }: ConfirmDialogProps) {
  return (
    <div className="confirm-dialog" role="dialog" aria-modal="true">
      <h3>{title}</h3>
      {description ? <p>{description}</p> : null}
      {actions ? <div className="confirm-dialog__actions">{actions}</div> : null}
    </div>
  );
}
