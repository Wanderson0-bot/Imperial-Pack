import type { PageHeaderProps } from '../types';
export function PageHeader({ title, description, actions }: PageHeaderProps) {
  return <header className="page-header"><div className="page-header__content"><span className="page-header__eyebrow">Imperial Pack &middot; Opera&ccedil;&otilde;es</span><h1>{title}</h1>{description ? <p className="page-header__description">{description}</p> : null}</div>{actions ? <div className="page-header__actions">{actions}</div> : null}</header>;
}
