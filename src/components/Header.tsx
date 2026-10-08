import type { ReactNode } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useState } from 'react';
import { authService } from '../services/authService';
type HeaderProps = { variant?: 'shell' | 'inline'; title?: string; module?: string; breadcrumb?: string; actions?: ReactNode };
export function Header({ variant = 'inline', title, module, breadcrumb = 'Opera\u00e7\u00f5es internas', actions }: HeaderProps) {
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const navigate = useNavigate();
  const user = authService.getCurrentUser();
  const context = module ?? title ?? 'Opera\u00e7\u00e3o';
  if (variant === 'inline') return null;
  return <header className="workspace-header"><div className="workspace-header__context" aria-label={context}><span className="workspace-header__crumb">{breadcrumb}</span></div>
    <div className="workspace-header__toolbar">{actions ? <div className="header-tools">{actions}</div> : null}<span className="header-divider" /><button type="button" className="user-chip" aria-label="Abrir menu do usu&aacute;rio" aria-expanded={isProfileOpen} onClick={() => setIsProfileOpen((current) => !current)}><span className="user-chip__avatar">{user?.name.split(' ').map((part) => part[0]).slice(0, 2).join('') ?? 'IP'}</span><span className="user-chip__details"><strong>{user?.name ?? 'Usuário interno'}</strong><small>{user?.role ?? 'Sessão local'}</small></span><span className="user-chip__chevron" aria-hidden="true">&#8964;</span></button>
      {isProfileOpen ? <div className="profile-menu" role="menu"><span className="profile-menu__label">Conta</span><Link to="/configuracoes" role="menuitem" onClick={() => setIsProfileOpen(false)}>Configura&ccedil;&otilde;es</Link><Link to="/usuarios" role="menuitem" onClick={() => setIsProfileOpen(false)}>Usu&aacute;rios e permiss&otilde;es</Link><button type="button" role="menuitem" onClick={() => { void authService.signOut(); navigate('/acesso', { replace: true }); }}>Sair</button><span className="profile-menu__label">Autentica&ccedil;&atilde;o local provis&oacute;ria</span></div> : null}
    </div></header>;
}
