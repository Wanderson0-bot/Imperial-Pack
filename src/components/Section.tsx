import type { ReactNode } from 'react';
type SectionProps = { title?: string; description?: string; actions?: ReactNode; children: ReactNode; className?: string };
export function Section({ title, description, actions, children, className = '' }: SectionProps) {
  return <section className={`workspace-section ${className}`.trim()}>
    {(title || description || actions) ? <header className="workspace-section__header"><div>{title ? <h3>{title}</h3> : null}{description ? <p>{description}</p> : null}</div>{actions ? <div className="workspace-section__actions">{actions}</div> : null}</header> : null}
    <div className="workspace-section__body">{children}</div>
  </section>;
}
