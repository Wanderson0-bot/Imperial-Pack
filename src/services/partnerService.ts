import type { Customer, PartnerProfile, PartnerPurchaseRecord, PredictionResult, ReplenishmentPrediction } from '../types';
import { apiRequest } from './apiClient';
import { customerService } from './customerService';

export const partnerService = {
  getCandidates: async (): Promise<Customer[]> => customerService.getAll(),
  getProfiles: async (): Promise<PartnerProfile[]> => {
    const rows = await apiRequest<Array<{ id: string; customer: { id: string }; status: string; activated_at?: string; conditions?: Record<string, unknown> | null; cycle?: { cycle_type: PartnerProfile['cycle']; custom_days?: number | null } | null }>>('/partners');
    return rows.map((row) => ({ partnerId: row.id, customerId: row.customer.id, status: row.status === 'ACTIVE' ? 'active' : 'inactive', activatedAt: row.activated_at ?? '', cycle: row.cycle?.cycle_type, customCycleDays: row.cycle?.custom_days ?? undefined, conditions: row.conditions ? { discountPercent: Number(row.conditions.discount_percent ?? 0), paymentTermDays: Number(row.conditions.payment_term_days ?? 0), paymentMethod: String(row.conditions.payment_method ?? ''), creditLimit: Number(row.conditions.credit_limit ?? 0), notes: String(row.conditions.notes ?? '') } : undefined }));
  },
  activate: async (customerId: string): Promise<PartnerProfile> => {
    const row = await apiRequest<{ id: string; customer_id: string; status: string; activated_at: string }>('/partners', { method: 'POST', body: JSON.stringify({ customer_id: customerId }) });
    return { partnerId: row.id, customerId: row.customer_id, status: row.status === 'ACTIVE' ? 'active' : 'inactive', activatedAt: row.activated_at };
  },
  setCycle: async (customerId: string, cycle: PartnerProfile['cycle'], customCycleDays?: number): Promise<void> => {
    const partner = (await partnerService.getProfiles()).find((profile) => profile.customerId === customerId && profile.status === 'active');
    if (!partner) throw new Error('Imperial Partner não encontrado.');
    if (!partner.partnerId) throw new Error('Identificador de parceiro indisponível.');
    await apiRequest(`/partners/${partner.partnerId}/cycle`, { method: 'PUT', body: JSON.stringify({ cycle_type: cycle ?? 'monthly', custom_days: customCycleDays ?? null }) });
  },
  getPurchaseHistory: async (customerId: string): Promise<PartnerPurchaseRecord[]> => {
    const partner = (await partnerService.getProfiles()).find((profile) => profile.customerId === customerId && profile.status === 'active');
    if (!partner?.partnerId) return [];
    const rows = await apiRequest<Array<{ partner_id: string; customer_id: string; product_id: string; quantity: number | string; purchased_at: string; unit_price: number | string; unit_cost?: number | string | null; order_id: string; source: PartnerPurchaseRecord['source']; interval_since_previous_days?: number | null }>>(`/partners/${partner.partnerId}/consumption`);
    return rows.map((row) => ({ customerId: row.customer_id, productId: row.product_id, quantity: Number(row.quantity), purchasedAt: row.purchased_at.slice(0, 10), unitPrice: Number(row.unit_price), unitCost: row.unit_cost == null ? undefined : Number(row.unit_cost), orderId: row.order_id, source: row.source, intervalSincePreviousDays: row.interval_since_previous_days ?? undefined }));
  },
  getPredictions: async (customerId: string): Promise<ReplenishmentPrediction[]> => {
    const partner = (await partnerService.getProfiles()).find((profile) => profile.customerId === customerId && profile.status === 'active');
    if (!partner?.partnerId) return [];
    const result = await apiRequest<{ predictions: Array<{ id: string; product_id: string; payload: Record<string, unknown>; model_version: string; generated_at: string }> }>(`/partners/${partner.partnerId}/predictions`);
    return result.predictions.map((row) => ({
      customerId,
      productId: row.product_id,
      predictedConsumption: Number(row.payload.predicted_consumption ?? 0),
      recommendedQuantity: Number(row.payload.recommended_quantity ?? 0),
      trend: ['increasing', 'stable', 'decreasing'].includes(String(row.payload.trend)) ? row.payload.trend as ReplenishmentPrediction['trend'] : 'unknown',
      confidence: ['high', 'medium', 'low'].includes(String(row.payload.confidence)) ? row.payload.confidence as ReplenishmentPrediction['confidence'] : 'insufficient-data',
      modelVersion: row.model_version,
      generatedAt: row.generated_at,
      explanation: typeof row.payload.explanation === 'string' ? row.payload.explanation : undefined,
    }));
  },
  recordPredictionResult: async (result: PredictionResult): Promise<void> => {
    await apiRequest(`/partners/predictions/${result.predictionId}/evaluation`, { method: 'POST', body: JSON.stringify({ actual_value: result.actualQuantity ?? null, actual_at: result.actualReplenishmentAt ? new Date(`${result.actualReplenishmentAt}T12:00:00`).toISOString() : null }) });
  },
};
