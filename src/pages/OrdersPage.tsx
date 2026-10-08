import { useEffect, useState } from 'react';
import { DataTable } from '../components/DataTable';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { Header } from '../components/Header';
import { LoadingState } from '../components/LoadingState';
import { PageHeader } from '../components/PageHeader';
import { StatusBadge } from '../components/StatusBadge';
import { orderService } from '../services/orderService';
import type { Order } from '../types';

const money = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });

export function OrdersPage() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [error, setError] = useState('');
  const [feedback, setFeedback] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [cancellingId, setCancellingId] = useState('');
  const refresh = async () => setOrders(await orderService.getAll());
  useEffect(() => { void refresh().catch(() => setError('Não foi possível carregar os pedidos da API.')).finally(() => setIsLoading(false)); }, []);

  const cancelOrder = async (order: Order) => {
    if (!window.confirm(`Cancelar o pedido ${order.id}? Se o estoque já foi comprometido, ele será devolvido.`)) return;
    setCancellingId(order.id);
    setError('');
    try {
      await orderService.updateStatus(order.id, 'Cancelado');
      setFeedback(`Pedido ${order.id} cancelado.`);
      await refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Não foi possível cancelar o pedido.');
    } finally { setCancellingId(''); }
  };

  return <><Header title="Pedidos" breadcrumb="Comercial / Vendas" /><div className="page-shell">
    <PageHeader title="Pedidos e vendas" description="Histórico comercial vinculado a clientes e produtos existentes." actions={<span className="page-header__meta">{orders.length} pedidos</span>} />
    {feedback ? <div className="inline-feedback" role="status">{feedback}</div> : null}
    {error ? <ErrorState message={error} /> : null}
    <section className="panel"><div className="panel__header"><div><h3>Pedidos registrados</h3><p className="panel__description">Pedidos novos não movimentam estoque até a confirmação.</p></div></div>
      {isLoading ? <LoadingState message="Carregando pedidos…" /> : orders.length ? <DataTable label="Pedidos comerciais" columns={<><th>Pedido</th><th>Cliente</th><th>Data</th><th>Itens</th><th>Valor</th><th>Origem</th><th>Status</th><th>Ações</th></>} rows={orders.map((order) => <tr key={order.id}><td><strong>{order.id}</strong></td><td>{order.customer}</td><td>{new Date(`${order.date}T12:00:00`).toLocaleDateString('pt-BR')}</td><td>{order.items}</td><td>{money.format(order.value)}</td><td>{order.source ?? '—'}</td><td><StatusBadge tone="neutral">{order.status}</StatusBadge></td><td>{order.status !== 'Cancelado' && order.status !== 'Entregue' ? <button className="btn btn--secondary" type="button" disabled={cancellingId === order.id} onClick={() => void cancelOrder(order)}>{cancellingId === order.id ? 'Cancelando…' : 'Cancelar'}</button> : '—'}</td></tr>)} /> : <EmptyState title="Nenhum pedido registrado" description="Registre uma venda pela carteira de clientes para iniciar o histórico comercial." />}
    </section>
  </div></>;
}