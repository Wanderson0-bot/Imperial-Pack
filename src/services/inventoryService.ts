import type { InventoryMovement, Product } from '../types';
import { apiRequest } from './apiClient';

export const inventoryService = {
  getMovements: async (productId?: string): Promise<InventoryMovement[]> => {
    const rows = await apiRequest<Array<{ id: string; product_id: string; movement_type: string; quantity: number | string; occurred_at: string; reason: string }>>('/inventory/movements');
    return rows.filter((row) => !productId || row.product_id === productId).map((row) => ({ id: row.id, productId: row.product_id, type: row.movement_type === 'IN' ? 'entrada' : row.movement_type === 'OUT' ? 'saída' : 'ajuste', quantity: Number(row.quantity), date: row.occurred_at.slice(0, 10), reason: row.reason }));
  },
  getBalances: async (): Promise<Array<{ productId: string; name: string; current: number; minimum: number }>> => {
    const rows = await apiRequest<Array<{ product_id: string; product_name: string; quantity: number | string; minimum: number | string }>>('/inventory/balances');
    return rows.map((row) => ({ productId: row.product_id, name: row.product_name, current: Number(row.quantity), minimum: Number(row.minimum) }));
  },
  adjust: async (productId: string, quantityDelta: number, reason: string): Promise<void> => {
    await apiRequest('/inventory/adjustments', { method: 'POST', body: JSON.stringify({ product_id: productId, quantity_delta: quantityDelta, reason }) });
  },
  getStatus: async (product: Product): Promise<'Normal' | 'Baixo' | 'Crítico' | 'Sem estoque'> => {
    if (product.stock <= 0) return 'Sem estoque';
    if (product.stock <= product.minStock * 0.5) return 'Crítico';
    if (product.stock <= product.minStock) return 'Baixo';
    return 'Normal';
  },
};
