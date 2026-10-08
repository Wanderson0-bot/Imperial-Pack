import { describe, expect, it, vi } from 'vitest';
import { customerService } from './customerService';
import { orderService } from './orderService';
import { reportService } from './reportService';
import type { Order, OrderStatus } from '../types';

vi.mock('./customerService', () => ({
  customerService: { getAll: vi.fn() },
}));

vi.mock('./orderService', () => ({
  orderService: { getAll: vi.fn() },
}));

describe('reportService', () => {
  it('excludes new and cancelled orders from realized sales', async () => {
    const createOrder = (id: string, status: OrderStatus, value: number): Order => ({
      id,
      customer: 'Test Customer',
      customerId: 'test-customer',
      value,
      status,
      date: '2026-10-05',
      items: 1,
      lineItems: [],
    });

    vi.mocked(customerService.getAll).mockResolvedValue([]);
    vi.mocked(orderService.getAll).mockResolvedValue([
      createOrder('new', 'Novo', 10),
      createOrder('confirmed', 'Confirmado', 20),
      createOrder('preparing', 'Em separação', 30),
      createOrder('ready', 'Pronto', 40),
      createOrder('delivered', 'Entregue', 50),
      createOrder('cancelled', 'Cancelado', 60),
    ]);

    const overview = await reportService.getOverview();

    expect(overview.orders.map((order) => order.id)).toEqual([
      'confirmed',
      'preparing',
      'ready',
      'delivered',
    ]);
  });
});
