import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Header } from '../components/Header';
import { PageHeader } from '../components/PageHeader';
import { StatusBadge } from '../components/StatusBadge';
import { ErrorState } from '../components/ErrorState';
import { inventoryService } from '../services/inventoryService';
import { orderService } from '../services/orderService';
import { purchaseService } from '../services/purchaseService';
import { productService } from '../services/productService';
import type { InventoryMovement, Order, Product, Purchase } from '../types';
const currency = (value: number) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value);
const dateLabel = (value: string) => new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: 'short' }).format(new Date(`${value}T12:00:00`));
type Activity = { id: string; date: string; kind: string; title: string; detail: string; href: string; tone: 'info' | 'success' | 'warning' };
export function DashboardPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [movements, setMovements] = useState<InventoryMovement[]>([]);
  const [purchases, setPurchases] = useState<Purchase[]>([]);
  const [loadError, setLoadError] = useState('');
  useEffect(() => {
    let active = true;
    void Promise.all([productService.getAll(), orderService.getAll(), inventoryService.getMovements(), purchaseService.getAll()]).then(([nextProducts, nextOrders, nextMovements, nextPurchases]) => {
      if (!active) return;
      setProducts(nextProducts); setOrders(nextOrders); setMovements(nextMovements); setPurchases(nextPurchases);
    }).catch(() => { if (active) setLoadError('Não foi possível carregar os dados operacionais da API.'); });
    return () => { active = false; };
  }, []);
  const lowStock = useMemo(() => products.filter((product) => product.stock <= product.minStock).sort((a, b) => a.stock - b.stock), [products]);
  const pendingPurchases = purchases.filter((purchase) => !['aprovada', 'recebida', 'conclu\u00edda', 'concluida'].includes(purchase.status.toLocaleLowerCase()));
  const needsPricing = products.filter((product) => !Number.isFinite(product.price) || product.price <= 0);
  const operationalOrders = orders.filter((order) => !['conclu\u00eddo', 'concluido', 'cancelado', 'entregue'].includes(order.status.toLocaleLowerCase()));
  const salesTotal = orders.reduce((sum, order) => sum + order.value, 0);
  const stockValue = products.reduce((sum, product) => sum + product.cost * product.stock, 0);
  const activities: Activity[] = [
    ...orders.map((order) => ({ id: `order-${order.id}`, date: order.date, kind: 'PEDIDO', title: `${order.id} \u00b7 ${order.customer}`, detail: `${order.items} itens \u00b7 ${currency(order.value)} \u00b7 ${order.status}`, href: '/pedidos', tone: 'info' as const })),
    ...purchases.map((purchase) => ({ id: `purchase-${purchase.id}`, date: purchase.date, kind: 'COMPRA', title: `${purchase.id} \u00b7 ${purchase.supplier}`, detail: `${purchase.items.length} itens \u00b7 ${currency(purchase.totalValue)} \u00b7 ${purchase.status}`, href: '/compras/nova', tone: 'success' as const })),
    ...movements.map((movement) => { const product = products.find((item) => item.id === movement.productId); return { id: `movement-${movement.id}`, date: movement.date, kind: 'ESTOQUE', title: product?.name ?? movement.productId, detail: `${movement.type} de ${movement.quantity} \u00b7 ${movement.reason}`, href: '/estoque', tone: 'warning' as const }; }),
  ].sort((a, b) => b.date.localeCompare(a.date)).slice(0, 6);
  const topProducts = [...products].sort((a, b) => (a.stock - a.minStock) - (b.stock - b.minStock)).slice(0, 4);
  const attentionCount = lowStock.length + needsPricing.length + pendingPurchases.length + operationalOrders.length;
  return <><Header title="Vis&atilde;o geral" breadcrumb="Vis&atilde;o geral / Centro de comando" /><div className="page-shell command-page">
    <PageHeader title="Vis&atilde;o geral" description="Acompanhe o que est&aacute; acontecendo e decida o pr&oacute;ximo passo." actions={<span className="data-status"><span className="data-status__dot" />Dados operacionais</span>} />
    {loadError ? <ErrorState message={loadError} /> : null}
    <section className="command-summary" aria-label="Resumo operacional"><div className="command-summary__result"><span className="command-kicker">RESULTADO &middot; PEDIDOS REGISTRADOS</span><strong className="command-summary__sales">{currency(salesTotal)}</strong><span className="command-summary__caption">{orders.length} pedidos na base atual</span></div><div className="command-summary__ops"><div><span className="command-kicker">OPERA&Ccedil;&Atilde;O</span><strong>{operationalOrders.length}</strong><small>pedidos em andamento</small></div><div><span className="command-kicker">ESTOQUE</span><strong>{lowStock.length}</strong><small>produtos no m&iacute;nimo ou abaixo</small></div><div><span className="command-kicker">COMPRAS</span><strong>{pendingPurchases.length}</strong><small>compras pendentes</small></div><div><span className="command-kicker">VALOR EM ESTOQUE</span><strong>{currency(stockValue)}</strong><small>pelo custo registrado</small></div></div></section>
    <section className="command-attention" aria-labelledby="attention-heading"><div className="command-section-heading"><div><span className="command-kicker">PR&Oacute;XIMOS PASSOS</span><h2 id="attention-heading">Precisa de aten&ccedil;&atilde;o</h2></div><span className="command-attention__count">{attentionCount} itens</span></div>
      {attentionCount === 0 ? <p className="command-empty">Nenhuma pend&ecirc;ncia operacional identificada.</p> : <div className="command-issues">
        {lowStock.slice(0, 4).map((product) => <article className="command-issue" key={`stock-${product.id}`}><StatusBadge tone={product.stock === 0 ? 'danger' : 'warning'}>{product.stock === 0 ? 'Sem estoque' : 'Estoque baixo'}</StatusBadge><div><strong>{product.name}</strong><p>{product.stock} {product.unit} dispon&iacute;veis &middot; m&iacute;nimo {product.minStock}</p></div><Link to="/estoque" className="command-link">Ver estoque <span aria-hidden="true">&#8599;</span></Link></article>)}
        {needsPricing.map((product) => <article className="command-issue" key={`pricing-${product.id}`}><StatusBadge tone="warning">Precifica&ccedil;&atilde;o</StatusBadge><div><strong>{product.name}</strong><p>Produto sem pre&ccedil;o de venda v&aacute;lido</p></div><Link to="/precificacao" className="command-link">Revisar pre&ccedil;o <span aria-hidden="true">&#8599;</span></Link></article>)}
        {pendingPurchases.map((purchase) => <article className="command-issue" key={`pending-${purchase.id}`}><StatusBadge tone="info">Compra pendente</StatusBadge><div><strong>{purchase.supplier}</strong><p>{purchase.id} &middot; {purchase.status} &middot; {currency(purchase.totalValue)}</p></div><Link to="/compras/nova" className="command-link">Ver compras <span aria-hidden="true">&#8599;</span></Link></article>)}
        {operationalOrders.slice(0, 3).map((order) => <article className="command-issue" key={`pending-order-${order.id}`}><StatusBadge tone="info">{`Pedido \u00b7 ${order.status}`}</StatusBadge><div><strong>{order.customer}</strong><p>{order.id} &middot; {order.items} itens &middot; {currency(order.value)}</p></div><Link to="/pedidos" className="command-link">Ver pedido <span aria-hidden="true">&#8599;</span></Link></article>)}
      </div>}
    </section>
    <div className="command-lower-grid"><section className="command-activity" aria-labelledby="activity-heading"><div className="command-section-heading"><div><span className="command-kicker">O QUE MUDOU</span><h2 id="activity-heading">Atividade operacional</h2></div><Link className="command-link" to="/pedidos">Abrir pedidos <span aria-hidden="true">&#8599;</span></Link></div>
      {activities.length ? <ol className="command-timeline">{activities.map((activity) => <li key={activity.id}><span className={`command-timeline__marker command-timeline__marker--${activity.tone}`} /><time>{dateLabel(activity.date)}</time><div><span className="command-kicker">{activity.kind}</span><strong>{activity.title}</strong><p>{activity.detail}</p></div><Link to={activity.href} aria-label={`Abrir ${activity.kind.toLocaleLowerCase()}`} className="command-timeline__arrow">&#8599;</Link></li>)}</ol> : <p className="command-empty">Ainda n&atilde;o h&aacute; atividade registrada.</p>}
    </section><aside className="command-side"><section className="command-performance" aria-labelledby="performance-heading"><div className="command-section-heading"><div><span className="command-kicker">ACOMPANHAMENTO</span><h2 id="performance-heading">Produtos e estoque</h2></div></div>
      {topProducts.length ? <div className="command-products">{topProducts.map((product) => { const low = product.stock <= product.minStock; return <div className="command-product" key={product.id}><div><Link to={`/produtos/${product.id}`}><strong>{product.name}</strong></Link><small>{product.category} &middot; {currency(product.price)} / {product.unit}</small></div><div className="command-product__stock"><strong>{product.stock}</strong><small>em estoque</small>{low ? <StatusBadge tone="warning">Repor</StatusBadge> : null}</div></div>; })}</div> : <p className="command-empty">Cadastre produtos para acompanhar o cat&aacute;logo.</p>}
      <Link className="command-link command-performance__all" to="/produtos">Ver produtos <span aria-hidden="true">&#8599;</span></Link>
    </section></aside></div>
  </div></>;
}
