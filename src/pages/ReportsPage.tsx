import { useEffect, useState } from 'react';
import { Header } from '../components/Header';
import { PageHeader } from '../components/PageHeader';
import { Section } from '../components/Section';
import { DataTable } from '../components/DataTable';
import { LoadingState } from '../components/LoadingState';
import { reportService } from '../services/reportService';
import type { Customer, Order, Product } from '../types';
import { productService } from '../services/productService';
const currency = (value: number) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value);
export function ReportsPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  useEffect(() => { let isMounted = true; void Promise.all([productService.getAll(), reportService.getOverview()]).then(([nextProducts, overview]) => { if (isMounted) { setProducts(nextProducts); setCustomers(overview.customers); setOrders(overview.orders); } }).catch(() => { if (isMounted) setProducts([]); }).finally(() => { if (isMounted) setIsLoading(false); }); return () => { isMounted = false; }; }, []);
  const sales = orders.reduce((total, order) => total + order.value, 0);
  const stockValue = products.reduce((total, product) => total + product.cost * product.stock, 0);
  const averageMargin = products.reduce((total, product) => total + product.margin, 0) / Math.max(products.length, 1);
  const healthyStock = Math.round((products.filter((product) => product.stock > product.minStock).length / Math.max(products.length, 1)) * 100);
  return <><Header title="Relat&oacute;rios" breadcrumb="Intelig&ecirc;ncia / Relat&oacute;rios" /><div className="page-shell"><PageHeader title="Relat&oacute;rios" description="Leitura r&aacute;pida das m&eacute;tricas registradas em vendas, estoque e cat&aacute;logo." actions={<span className="page-header__meta">Base local &middot; sem conex&atilde;o externa</span>} />{isLoading ? <LoadingState message="Consolidando informa&ccedil;&otilde;es…" /> : <>
    <section className="report-overview" aria-label="Resumo dos indicadores"><div className="report-overview__lead"><span className="eyebrow">Vendas registradas</span><strong>{currency(sales)}</strong><small>Volume somado dos pedidos dispon&iacute;veis</small></div><dl className="report-facts"><div><dt>Valor em estoque</dt><dd>{currency(stockValue)}</dd></div><div><dt>Margem m&eacute;dia</dt><dd>{averageMargin.toFixed(1)}%</dd></div><div><dt>Produtos cadastrados</dt><dd>{products.length}</dd></div><div><dt>Estoque acima do m&iacute;nimo</dt><dd>{healthyStock}%</dd></div><div><dt>Clientes cadastrados</dt><dd>{customers.length}</dd></div></dl></section>
    <Section title="Vis&atilde;o do cat&aacute;logo" description="Quantidade e margem registradas para cada produto."><DataTable label="Produtos e estoque" columns={<><th>Produto</th><th>Categoria</th><th>Estoque atual</th><th>Estoque m&iacute;nimo</th><th>Margem</th></>} rows={products.map((product) => <tr key={product.id}><td><strong>{product.name}</strong></td><td>{product.category}</td><td>{product.stock} {product.unit}</td><td>{product.minStock} {product.unit}</td><td>{product.margin.toFixed(1)}%</td></tr>)} /></Section>
  </>}</div></>;
}
