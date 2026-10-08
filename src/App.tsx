import { Navigate, Route, Routes } from 'react-router-dom';
import { AppShell } from './layouts/AppShell';
import { DashboardPage } from './pages/DashboardPage';
import { PurchasePage } from './pages/PurchasePage';
import { PricingPage } from './pages/PricingPage';
import { ProductsPage } from './pages/ProductsPage';
import { ProductDetailPage } from './pages/ProductDetailPage';
import { InventoryPage } from './pages/InventoryPage';
import { OrdersPage } from './pages/OrdersPage';
import { CustomersPage } from './pages/CustomersPage';
import { SuppliersPage } from './pages/SuppliersPage';
import { PartnerPage } from './pages/PartnerPage';
import { IntelligencePage } from './pages/IntelligencePage';
import { ReportsPage } from './pages/ReportsPage';
import { SettingsPage } from './pages/SettingsPage';
import { UsersPage } from './pages/UsersPage';
import { AccessPage } from './pages/AccessPage';
import { OperationalSignalsPage } from './pages/OperationalSignalsPage';
import { ProtectedRoute } from './components/ProtectedRoute';

function App() {
  return (
    <Routes>
      <Route path="/acesso" element={<AccessPage />} />
      <Route element={<ProtectedRoute />}>
      <Route element={<AppShell />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/compras/nova" element={<PurchasePage />} />
        <Route path="/precificacao" element={<PricingPage />} />
        <Route path="/produtos" element={<ProductsPage />} />
        <Route path="/produtos/:id" element={<ProductDetailPage />} />
        <Route path="/estoque" element={<InventoryPage />} />
        <Route path="/pedidos" element={<OrdersPage />} />
        <Route path="/clientes" element={<CustomersPage />} />
        <Route path="/fornecedores" element={<SuppliersPage />} />
        <Route path="/imperial-partner" element={<PartnerPage />} />
        <Route path="/alertas" element={<OperationalSignalsPage />} />
        <Route path="/inteligencia" element={<IntelligencePage />} />
        <Route path="/relatorios" element={<ReportsPage />} />
        <Route path="/configuracoes" element={<SettingsPage />} />
        <Route path="/usuarios" element={<UsersPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
      </Route>
    </Routes>
  );
}

export default App;
