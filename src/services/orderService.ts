import type { Order } from '../types';
import { customerService } from './customerService';
import { apiRequest } from './apiClient';

type OrderDto = { id: string; customer_id: string; ordered_at: string; status: string; subtotal: number | string; total: number | string; source: string; items: Array<{ product_id: string; product_name_snapshot: string; unit_price_snapshot: number | string; quantity: number | string; subtotal: number | string }> };
const statusFromApi = (status: string): Order['status'] => ({ NEW: 'Novo', CONFIRMED: 'Confirmado', PREPARING: 'Em separação', READY: 'Pronto', DELIVERED: 'Entregue', CANCELLED: 'Cancelado' }[status] as Order['status']) ?? 'Novo';

export const orderService = {
  getById: async (id: string): Promise<Order> => {
    const [row, customers] = await Promise.all([apiRequest<OrderDto>(`/orders/${id}`), customerService.getAll()]);
    return { id: row.id, customer: customers.find((customer) => customer.id === row.customer_id)?.company ?? row.customer_id, customerId: row.customer_id, value: Number(row.total), status: statusFromApi(row.status), date: row.ordered_at.slice(0, 10), items: row.items.length, lineItems: row.items.map((item) => ({ productId: item.product_id, quantity: Number(item.quantity), unitPrice: Number(item.unit_price_snapshot) })), source: row.source.toLowerCase() as Order['source'] };
  },
  getAll: async (): Promise<Order[]> => {
    const [rows, customers] = await Promise.all([apiRequest<OrderDto[]>('/orders'), customerService.getAll()]);
    return rows.map((row) => ({ id: row.id, customer: customers.find((customer) => customer.id === row.customer_id)?.company ?? row.customer_id, customerId: row.customer_id, value: Number(row.total), status: statusFromApi(row.status), date: row.ordered_at.slice(0, 10), items: row.items.length, lineItems: row.items.map((item) => ({ productId: item.product_id, quantity: Number(item.quantity), unitPrice: Number(item.unit_price_snapshot) })), source: row.source.toLowerCase() as Order['source'] }));
  },
  create: async (order: Order): Promise<Order> => {
    if (!order.customerId || !order.lineItems?.length) throw new Error('Pedido requer cliente e itens detalhados.');
    const dto = await apiRequest<OrderDto>('/orders', { method: 'POST', body: JSON.stringify({ customer_id: order.customerId, ordered_at: new Date(`${order.date}T12:00:00`).toISOString(), status: ({ Novo: 'NEW', Confirmado: 'CONFIRMED', 'Em separação': 'PREPARING', Pronto: 'READY', Entregue: 'DELIVERED', Cancelado: 'CANCELLED' } as const)[order.status] ?? 'NEW', notes: '', source: order.source?.toUpperCase() ?? 'INTERNAL', items: order.lineItems.map((item) => ({ product_id: item.productId, quantity: item.quantity })) }) });
    const customers = await customerService.getAll();
    return { id: dto.id, customer: customers.find((customer) => customer.id === dto.customer_id)?.company ?? dto.customer_id, customerId: dto.customer_id, value: Number(dto.total), status: statusFromApi(dto.status), date: dto.ordered_at.slice(0, 10), items: dto.items.length, lineItems: dto.items.map((item) => ({ productId: item.product_id, quantity: Number(item.quantity), unitPrice: Number(item.unit_price_snapshot) })), source: dto.source.toLowerCase() as Order['source'] };
  },
  createSale: async (input: { customerId: string; customerName: string; date: string; notes?: string; items: Array<{ productId: string; quantity: number }> }): Promise<Order> => {
    if (!input.customerId || !input.items.length) throw new Error('Venda requer cliente existente e pelo menos um produto.');
    const consolidated = new Map<string, number>();
    for (const item of input.items) consolidated.set(item.productId, (consolidated.get(item.productId) ?? 0) + item.quantity);
    const dto = await apiRequest<OrderDto>('/orders', { method: 'POST', body: JSON.stringify({ customer_id: input.customerId, ordered_at: new Date(`${input.date}T12:00:00`).toISOString(), status: 'NEW', source: 'INTERNAL', notes: input.notes || null, items: [...consolidated].map(([product_id, quantity]) => ({ product_id, quantity })) }) });
    return { id: dto.id, customer: input.customerName, customerId: dto.customer_id, value: Number(dto.total), status: statusFromApi(dto.status), date: dto.ordered_at.slice(0, 10), items: dto.items.length, lineItems: dto.items.map((item) => ({ productId: item.product_id, quantity: Number(item.quantity), unitPrice: Number(item.unit_price_snapshot) })), source: dto.source.toLowerCase() as Order['source'] };
  },
  updateStatus: async (id: string, status: Order['status']): Promise<void> => {
    const apiStatus = ({ Novo: 'NEW', Confirmado: 'CONFIRMED', 'Em separação': 'PREPARING', Pronto: 'READY', Entregue: 'DELIVERED', Cancelado: 'CANCELLED' } as const)[status];
    await apiRequest(`/orders/${id}/status`, { method: 'PATCH', body: JSON.stringify({ status: apiStatus }) });
  },
};
