import { apiRequest } from './apiClient';

export type IntelligenceStatus = {
  ml_configured: boolean;
  model_status: 'active' | 'awaiting_data' | 'error' | 'training';
  model_version: string | null;
  algorithm: string | null;
  trained_at: string | null;
  training_period: { start: string; end: string } | null;
  training_records: number;
  consumption_records: number;
  active_partners: number;
  products_with_history: number;
  stored_predictions: number;
  evaluated_predictions: number;
  eligible_partner_products: number;
  insufficient_partner_products: number | 'not_evaluated';
  validation_metrics: { interval_days: { count: number; mae: number; rmse: number }; next_quantity: { count: number; mae: number; rmse: number } } | null;
  evaluation_metrics: { count: number; mae: number | null; rmse: number | null; mape_percent: number | null; interval_error_days: { count: number; mae: number | null; rmse: number | null } };
  message: string;
};

export const intelligenceService = {
  getStatus: (): Promise<IntelligenceStatus> => apiRequest('/intelligence/status'),
  train: () => apiRequest<{ status: string; version?: string; eligible_pairs?: number; insufficient_pairs?: number; metrics?: IntelligenceStatus['validation_metrics']; message?: string }>('/intelligence/train', { method: 'POST' }),
};
