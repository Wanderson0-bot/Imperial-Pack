import type { ReplenishmentPrediction } from '../types';
import { partnerService } from './partnerService';
import { apiRequest } from './apiClient';

export type PartnerPredictionResult = {
  status: 'insufficient-data' | 'model-unavailable' | 'ready';
  predictions: ReplenishmentPrediction[];
  message?: string;
};

export const partnerPredictionService = {
  getForPartner: async (customerId: string): Promise<PartnerPredictionResult> => {
    const partner = (await partnerService.getProfiles()).find((profile) => profile.customerId === customerId && profile.status === 'active');
    if (!partner?.partnerId) return { status: 'insufficient-data', predictions: [], message: 'Parceiro sem histórico cadastrado.' };
    const result = await apiRequest<{ status: PartnerPredictionResult['status']; predictions: Array<{ id: string; product_id: string; payload: Record<string, unknown>; model_version: string; generated_at: string }>; message?: string }>(`/partners/${partner.partnerId}/predictions`);
    return {
      status: result.status,
      message: result.message,
      predictions: result.predictions.map((row) => ({
        customerId,
        productId: row.product_id,
        predictedConsumption: Number(row.payload.predicted_consumption ?? 0),
        recommendedQuantity: Number(row.payload.recommended_quantity ?? 0),
        replenishmentWindow: row.payload.replenishment_window && typeof row.payload.replenishment_window === 'object'
          ? row.payload.replenishment_window as ReplenishmentPrediction['replenishmentWindow'] : undefined,
        trend: ['increasing', 'stable', 'decreasing'].includes(String(row.payload.trend)) ? row.payload.trend as ReplenishmentPrediction['trend'] : 'unknown',
        confidence: ['high', 'medium', 'low'].includes(String(row.payload.confidence)) ? row.payload.confidence as ReplenishmentPrediction['confidence'] : 'insufficient-data',
        modelVersion: row.model_version,
        generatedAt: row.generated_at,
        explanation: typeof row.payload.explanation === 'string' ? row.payload.explanation : undefined,
      })),
    };
  },
};
