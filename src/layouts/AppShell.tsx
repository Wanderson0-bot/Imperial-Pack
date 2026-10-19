import { Outlet, useLocation } from 'react-router-dom';
import { Header } from '../components/Header';
import { Sidebar } from '../components/Sidebar';
import { SystemTutorial } from '../components/SystemTutorial';

const pageContext: Record<string, { label: string; breadcrumb: string }> = {
  '/': { label: 'Vis\u00e3o geral', breadcrumb: 'Vis\u00e3o geral / Centro de comando' },
  '/compras/nova': { label: 'Nova compra', breadcrumb: 'Compras / Nova compra' },
  '/precificacao': { label: 'Precifica\u00e7\u00e3o', breadcrumb: 'Cat\u00e1logo / Precifica\u00e7\u00e3o' },
  '/produtos': { label: 'Produtos', breadcrumb: 'Cat\u00e1logo / Produtos' },
  '/estoque': { label: 'Estoque', breadcrumb: 'Opera\u00e7\u00e3o / Estoque' },
  '/pedidos': { label: 'Pedidos', breadcrumb: 'Opera\u00e7\u00e3o / Pedidos' },
  '/clientes': { label: 'Clientes', breadcrumb: 'Comercial / Clientes' },
  '/fornecedores': { label: 'Fornecedores', breadcrumb: 'Comercial / Fornecedores' },
  '/imperial-partner': { label: 'Imperial Partner', breadcrumb: 'Comercial / Imperial Partner' },
  '/inteligencia': { label: 'Intelig\u00eancia', breadcrumb: 'Intelig\u00eancia / An\u00e1lises' },
  '/relatorios': { label: 'Relat\u00f3rios', breadcrumb: 'Intelig\u00eancia / Relat\u00f3rios' },
  '/configuracoes': { label: 'Configura\u00e7\u00f5es', breadcrumb: 'Administra\u00e7\u00e3o / Configura\u00e7\u00f5es' },
  '/usuarios': { label: 'Usu\u00e1rios', breadcrumb: 'Administra\u00e7\u00e3o / Usu\u00e1rios' },
  '/planejar': { label: 'Planejar', breadcrumb: 'Administra\u00e7\u00e3o / Planejar' },
};

export function AppShell() {
  const location = useLocation();
  const isProductDetail = location.pathname.startsWith('/produtos/');
  const segment = pageContext[location.pathname] ?? (isProductDetail
    ? { label: 'Detalhe do produto', breadcrumb: 'Cat\u00e1logo / Produtos / Detalhe' }
    : { label: 'Vis\u00e3o geral', breadcrumb: 'Vis\u00e3o geral / Centro de comando' });
  return <div className="app-shell"><a className="skip-link" href="#main-content">Ir para o conteúdo principal</a><Sidebar /><div className="app-shell__content"><Header variant="shell" module={segment.label} breadcrumb={segment.breadcrumb} actions={<SystemTutorial />} /><div className="workspace-canvas"><main className="app-main" id="main-content" tabIndex={-1}><Outlet /></main></div></div></div>;
}
