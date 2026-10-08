import { NavLink } from 'react-router-dom';
import { useState } from 'react';
import { Logo } from './Logo';

const menuGroups = [
  { label: 'Visi\u00e3o geral', items: [{ label: 'Visi\u00e3o geral', to: '/', icon: 'overview' }] },
  { label: 'Opera\u00e7\u00e3o', items: [{ label: 'Nova compra', to: '/compras/nova', icon: 'purchase' }, { label: 'Pedidos', to: '/pedidos', icon: 'orders' }, { label: 'Estoque', to: '/estoque', icon: 'inventory' }, { label: 'Alertas', to: '/alertas', icon: 'alerts' }] },
  { label: 'Cat\u00e1logo', items: [{ label: 'Produtos', to: '/produtos', icon: 'products' }, { label: 'Precifica\u00e7\u00e3o', to: '/precificacao', icon: 'pricing' }] },
  { label: 'Comercial', items: [{ label: 'Clientes', to: '/clientes', icon: 'customers' }, { label: 'Fornecedores', to: '/fornecedores', icon: 'suppliers' }, { label: 'Imperial Partner', to: '/imperial-partner', icon: 'partner' }] },
  { label: 'Intelig\u00eancia', items: [{ label: 'Intelig\u00eancia', to: '/inteligencia', icon: 'insights' }, { label: 'Relat\u00f3rios', to: '/relatorios', icon: 'reports' }] },
  { label: 'Administra\u00e7\u00e3o', items: [{ label: 'Usu\u00e1rios', to: '/usuarios', icon: 'users' }, { label: 'Configura\u00e7\u00f5es', to: '/configuracoes', icon: 'settings' }] },
];
const iconPaths: Record<string, string> = {
  overview: 'M3 3h7v7H3z M14 3h7v5h-7z M14 12h7v9h-7z M3 14h7v7H3z', purchase: 'M12 5v14 M5 12h14',
  orders: 'M8 6h13 M8 12h13 M8 18h13 M3 6h.01 M3 12h.01 M3 18h.01',
  inventory: 'M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z M3.3 7 12 12l8.7-5 M12 22V12',
  products: 'M20 7 12 3 4 7v10l8 4 8-4z M4 7l8 4 8-4 M12 21V11', pricing: 'M20 7 13 14 M10 7h.01 M17 14h.01 M6 18l12-12',
  customers: 'M16 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2 M10 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8 M20 8v6 M23 11h-6',
  suppliers: 'M3 21h18 M5 21V7l8-4v18 M19 21V11l-6-4 M9 9v.01 M9 12v.01 M9 15v.01 M9 18v.01', partner: 'M12 3 4 7v5c0 5 3.4 8 8 9 4.6-1 8-4 8-9V7z M9 12l2 2 4-4',
  insights: 'M3 3v18h18 M7 14l4-4 4 4 6-7', reports: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M8 13h8 M8 17h8',
  alerts: 'M12 22a2 2 0 0 0 2-2h-4a2 2 0 0 0 2 2z M18 16v-5a6 6 0 0 0-5-5.91V4a1 1 0 0 0-2 0v1.09A6 6 0 0 0 6 11v5l-2 2h16z',
  users: 'M16 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2 M10 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8 M20 8v6 M23 11h-6',
  settings: 'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-1.7 2.94-.09-.02a1.7 1.7 0 0 0-1.74.73l-.05.08h-3.4l-.05-.08a1.7 1.7 0 0 0-1.74-.73l-.09.02-1.7-2.94.06-.06A1.7 1.7 0 0 0 9.6 15l-.08-.05v-3.4l.08-.05a1.7 1.7 0 0 0-.34-1.88l-.06-.06 1.7-2.94.09.02a1.7 1.7 0 0 0 1.74-.73l.05-.08h3.4l.05.08a1.7 1.7 0 0 0 1.74.73l.09-.02 1.7 2.94-.06.06A1.7 1.7 0 0 0 19.6 11l.08.05v3.4z',
};
export function Sidebar() {
  const [isCollapsed, setIsCollapsed] = useState(false);
  return <aside className={`sidebar${isCollapsed ? ' sidebar--collapsed' : ''}`} aria-label="Navega&ccedil;&atilde;o principal">
    <div className="sidebar__header"><div className="sidebar__brand"><Logo variant="wordmarkWhite" surface="dark" className="brand-logo" /></div><button type="button" className="sidebar__collapse" onClick={() => setIsCollapsed((current) => !current)} aria-label={isCollapsed ? 'Expandir menu' : 'Recolher menu'} title={isCollapsed ? 'Expandir menu' : 'Recolher menu'}><svg viewBox="0 0 24 24" aria-hidden="true"><path d={isCollapsed ? 'm9 18 6-6-6-6' : 'm15 18-6-6 6-6'} /></svg></button></div>
    <nav className="sidebar__nav">{menuGroups.map((group) => <div className="sidebar__group" key={group.label}>{!isCollapsed ? <span className="sidebar__group-label">{group.label}</span> : null}{group.items.map((item) => <NavLink key={item.to} to={item.to} className={({ isActive }) => ['nav-item', isActive ? 'nav-item--active' : ''].join(' ')} end={item.to === '/'} title={item.label} aria-label={item.label}><svg className="nav-item__icon" viewBox="0 0 24 24" aria-hidden="true"><path d={iconPaths[item.icon]} /></svg>{!isCollapsed ? <span className="nav-item__label">{item.label}</span> : null}</NavLink>)}</div>)}</nav>
    <div className="sidebar__footer">{!isCollapsed ? <div className="sidebar__status"><small>Ambiente</small><strong><i /> Sistema operacional</strong></div> : null}</div>
  </aside>;
}
