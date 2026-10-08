import { apiRequest } from './apiClient';

export type OperationalAlert = {
  id: string;
  alert_type: string;
  entity_type: string;
  entity_id: string | null;
  entity_label: string;
  title: string;
  description: string;
  reason: string;
  priority: 'high' | 'medium' | 'low';
  status: 'OPEN' | 'RESOLVED' | 'IGNORED';
  detected_at: string;
};

export type OperationalOpportunity = {
  id: string;
  entity_type: string;
  entity_id: string | null;
  entity_label: string;
  title: string;
  description: string;
  action: string;
  evidence: Record<string, string | number | boolean | null>;
  status: 'OPEN' | 'DISMISSED' | 'ACTIONED' | 'EXPIRED';
  created_at: string;
};

export type OpportunitiesResult = { status: 'ready' | 'insufficient_data'; items: OperationalOpportunity[] };

export const operationalSignalsService = {
  getAlerts: () => apiRequest<OperationalAlert[]>('/alerts'),
  getOpportunities: () => apiRequest<OpportunitiesResult>('/opportunities'),
  updateAlert: (id: string, status: 'RESOLVED' | 'IGNORED') => apiRequest<OperationalAlert>(`/alerts/${id}`, { method: 'PATCH', body: JSON.stringify({ status }) }),
  updateOpportunity: (id: string, status: 'ACTIONED' | 'DISMISSED') => apiRequest<OperationalOpportunity>(`/opportunities/${id}`, { method: 'PATCH', body: JSON.stringify({ status }) }),
};