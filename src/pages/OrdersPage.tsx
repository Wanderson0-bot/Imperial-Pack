import { useEffect, useState } from 'react';
import { DataTable } from '../components/DataTable';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { Header } from '../components/Header';
import { LoadingState } from '../components/LoadingState';
import { PageHeader } from '../components/PageHeader';
import { StatusBadge } from '../components/StatusBadge';
import { orderService } from '../services/orderService';
import { formatOrderReference } from '../utils/orderReference';
import type { Order, OrderStatus } from '../types';

const money = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
const nextStep: Partial<Record<OrderStatus, { status: OrderStatus; label: string; question: string }>> = {
  Novo: { status: 'Confirmado', label: 'Aceitar pedido', question: 'Aceitar este pedido? O estoque será reservado.' },
  Confirmado: { status: 'Em separação', label: 'Iniciar separação', question: 'Iniciar a separação dos produtos deste pedido?' },
  'Em separação': { status: 'Pronto', label: 'Marcar como pronto', question: 'Marcar este pedido como pronto para entrega ou retirada?' },
  Pronto: { status: 'Entregue', label: 'Finalizar pedido', question: 'Finalizar este pedido e marcá-lo como entregue?' },
};

export function OrdersPage() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [error, setError] = useState('');
  const [feedback, setFeedback] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [updatingId, setUpdatingId] = useState('');
  const refresh = async () => setOrders(await orderService.getAll());
  useEffect(() => { void refresh().catch(() => setError('Não foi possível carregar os pedidos.')).finally(() => setIsLoading(false)); }, []);

  const advanceOrder = async (order: Order) => {
    const step = nextStep[order.status];
    if (!step || !window.confirm(`${step.question}\nPedido ${formatOrderReference(order.id)}.`)) return;
    setUpdatingId(order.id);
    setError('');
    setFeedback('');
    try {
      await orderService.updateStatus(order.id, step.status);
      setFeedback(`Pedido ${formatOrderReference(order.id)} atualizado: ${step.status.toLowerCase()}.`);
      await refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Não foi possível atualizar o pedido.');
    } finally { setUpdatingId(''); }
  };

  const cancelOrder = async (order: Order) => {
    if (!window.confirm(`Cancelar o pedido ${formatOrderReference(order.id)}? O estoque reservado será devolvido.`)) return;
    setUpdatingId(order.id);
    setError('');
    setFeedback('');
    try {
      await orderService.updateStatus(order.id, 'Cancelado');
      setFeedback(`Pedido ${formatOrderReference(order.id)} cancelado.`);
      await refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Não foi possível cancelar o pedido.');
    } finally { setUpdatingId(''); }
  };

  const pending = orders.filter((order) => nextStep[order.status]);

  return <><Header title="Pedidos" breadcrumb="Comercial / Vendas" /><div className="page-shell">
    <PageHeader title="Pedidos" description="Acompanhe cada pedido e avance uma etapa por vez." actions={<span className="page-header__meta">{pending.length} em andamento</span>} />
    {feedback ? <div className="inline-feedback" role="status">{feedback}</div> : null}
    {error ? <ErrorState message={error} /> : null}
    <section className="panel">
      <div className="panel__header"><div><h3>Como funciona</h3><p className="panel__description">Aceite o pedido, separe os produtos, marque como pronto e finalize quando entregar.</p></div></div>
      <div className="panel__header"><div><h3>Lista de pedidos</h3><p className="panel__description">O estoque é reservado ao aceitar. Cancelar devolve o estoque reservado.</p></div><span className="page-header__meta">{orders.length} pedidos</span></div>
      {isLoading ? <LoadingState message="Carregando pedidos…" /> : orders.length ? <DataTable label="Pedidos" columns={<><th>Pedido</th><th>Cliente</th><th>Data</th><th>Itens</th><th>Valor</th><th>Status</th><th>Próxima ação</th></>} rows={orders.map((order) => {
        const step = nextStep[order.status];
        return <tr key={order.id}><td><strong>{formatOrderReference(order.id)}</strong></td><td>{order.customer}</td><td>{new Date(`${order.date}T12:00:00`).toLocaleDateString('pt-BR')}</td><td>{order.items}</td><td>{money.format(order.value)}</td><td><StatusBadge tone="neutral">{order.status}</StatusBadge></td><td>{step ? <div className="purchase-row-actions"><button className="btn btn--primary" type="button" disabled={Boolean(updatingId)} onClick={() => void advanceOrder(order)}>{updatingId === order.id ? 'Atualizando…' : step.label}</button><button className="btn btn--secondary" type="button" disabled={Boolean(updatingId)} onClick={() => void cancelOrder(order)}>Cancelar</button></div> : order.status === 'Entregue' ? 'Concluído' : order.status === 'Cancelado' ? 'Cancelado' : '—'}</td></tr>;
      })} /> : <EmptyState title="Nenhum pedido ainda" description="Registre uma venda na página de Clientes. Os novos pedidos aparecerão aqui para você aceitar e acompanhar." />}
    </section>
  </div></>;
}
