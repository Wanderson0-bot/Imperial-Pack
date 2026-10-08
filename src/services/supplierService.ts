import type { Supplier } from '../types';
import { apiRequest } from './apiClient';

export type SupplierInput = {
  name: string;
  email?: string;
  phone?: string;
  location: string;
  notes?: string;
  minimum_order?: number;
  delivery_days?: number;
  product_ids: string[];
};

type SupplierAnalysisDto = {
  id: string;
  name: string;
  email: string | null;
  phone: string | null;
  location: string | null;
  minimumOrder: number | string | null;
  deliveryDays: number | null;
  contact: string;
  products: string[];
  productCosts: Array<{ id: string; name: string; last_cost: number | null; last_purchase: string | null }>;
  lastCost: number;
  history: number;
  lastPurchase: string;
  observations: string;
};

const mapSupplier = (row: SupplierAnalysisDto): Supplier => ({
  id: row.id,
  name: row.name,
  email: row.email,
  phone: row.phone,
  location: row.location,
  minimumOrder: row.minimumOrder == null ? null : Number(row.minimumOrder),
  deliveryDays: row.deliveryDays,
  contact: row.contact,
  products: row.products,
  productCosts: row.productCosts.map((item) => ({ id: item.id, name: item.name, lastCost: item.last_cost, lastPurchase: item.last_purchase })),
  lastCost: row.lastCost,
  history: row.history,
  lastPurchase: row.lastPurchase,
  observations: row.observations,
});

export const supplierService = {
  getActiveOptions: async (): Promise<Array<{ id: string; name: string }>> => {
    const rows = await apiRequest<Array<{ id: string; name: string; is_active: boolean }>>('/suppliers');
    return rows.filter((supplier) => supplier.is_active).map(({ id, name }) => ({ id, name }));
  },
  getAll: async (search?: string): Promise<Supplier[]> => {
    const query = search?.trim() ? `?search=${encodeURIComponent(search.trim())}` : '';
    const rows = await apiRequest<Array<{ id: string; name: string; product_ids: string[] }>>(`/suppliers${query}`);
    return Promise.all(rows.map(async (row) => {
      const data = await apiRequest<SupplierAnalysisDto>(`/suppliers/${row.id}/analysis`);
      const mapped = mapSupplier({ ...data, id: row.id, name: row.name });
      return { ...mapped, productIds: row.product_ids };
    }));
  },
  create: async (input: SupplierInput): Promise<void> => {
    await apiRequest('/suppliers', { method: 'POST', body: JSON.stringify({ ...input, location: input.location.trim() }) });
  },
  update: async (id: string, input: SupplierInput): Promise<void> => {
    await apiRequest(`/suppliers/${id}`, { method: 'PATCH', body: JSON.stringify({ ...input, location: input.location.trim() }) });
  },
};
