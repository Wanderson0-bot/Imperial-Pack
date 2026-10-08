import { productService } from './productService';
import type { Product, Purchase, PurchaseDraft } from '../types';
import { apiRequest } from './apiClient';

type PurchaseDto = {
  id: string;
  supplier_id: string;
  purchased_at: string;
  document_number: string | null;
  observations: string | null;
  products_value: number | string;
  discount_total: number | string;
  freight: number | string;
  other_costs: number | string;
  total: number | string;
  status: string;
  items: Array<{ id: string; product_id: string; quantity: number | string; unit_cost: number | string; discount: number | string; description: string | null; freight_share: number | string; other_cost_share: number | string; real_unit_cost: number | string }>;
};

const mapPurchase = (row: PurchaseDto, supplierName: string): Purchase => ({
  id: row.id,
  supplier: supplierName,
  date: row.purchased_at.slice(0, 10),
  documentNumber: row.document_number ?? undefined,
  observations: row.observations ?? undefined,
  productsValue: Number(row.products_value),
  discountTotal: Number(row.discount_total),
  totalValue: Number(row.total),
  freight: Number(row.freight),
  otherCosts: Number(row.other_costs),
  status: row.status === 'APPROVED' ? 'aprovada' : 'registrada',
  items: row.items.map((item) => ({
    id: item.id,
    productId: item.product_id,
    quantity: Number(item.quantity),
    paidValue: Number(item.unit_cost) * Number(item.quantity),
    unitCost: Number(item.unit_cost),
    discount: Number(item.discount),
    description: item.description ?? undefined,
    freightShare: Number(item.freight_share),
    otherCostShare: Number(item.other_cost_share),
    realUnitCost: Number(item.real_unit_cost),
    totalCost: Number(item.real_unit_cost) * Number(item.quantity),
  })),
});

export const purchaseService = {
  getAll: async (): Promise<Purchase[]> => {
    const [rows, suppliers] = await Promise.all([apiRequest<PurchaseDto[]>('/purchases'), apiRequest<Array<{ id: string; name: string }>>('/suppliers')]);
    return rows.map((row) => mapPurchase(row, suppliers.find((supplier) => supplier.id === row.supplier_id)?.name ?? row.supplier_id));
  },
  create: async (purchase: Purchase): Promise<Purchase> => {
    const suppliers = await apiRequest<Array<{ id: string; name: string }>>('/suppliers');
    const supplier = suppliers.find((item) => item.name === purchase.supplier);
    if (!supplier) throw new Error('Selecione um fornecedor cadastrado na API.');
    const result = await purchaseService.confirmPurchase({ supplierId: supplier.id, date: purchase.date, documentNumber: purchase.documentNumber, freight: purchase.freight, otherCosts: purchase.otherCosts, observations: purchase.observations, items: purchase.items.map(({ productId, quantity, unitCost, discount, description }) => ({ productId, quantity, unitCost, discount, description })) });
    return result.purchase;
  },
  confirmPurchase: async (draft: PurchaseDraft): Promise<{ purchase: Purchase; affectedProducts: Product[] }> => {
    const [suppliers, knownProducts] = await Promise.all([
      apiRequest<Array<{ id: string; name: string }>>('/suppliers'),
      productService.getAll(),
    ]);
    const supplier = suppliers.find((item) => item.id === draft.supplierId);
    if (!supplier) throw new Error('Selecione um fornecedor cadastrado na API.');
    const dto = await apiRequest<PurchaseDto>('/purchases', { method: 'POST', body: JSON.stringify({ supplier_id: supplier.id, purchased_at: new Date(`${draft.date}T12:00:00`).toISOString(), document_number: draft.documentNumber || null, observations: draft.observations || null, freight: draft.freight, other_costs: draft.otherCosts, items: draft.items.map((item) => ({ product_id: item.productId, quantity: item.quantity, unit_cost: item.unitCost, discount: item.discount, description: item.description || null })) }) });
    const affectedProducts = knownProducts.filter((product) => dto.items.some((item) => item.product_id === product.id));
    const purchase = mapPurchase(dto, supplier.name);
    return { purchase, affectedProducts };
  },
};
