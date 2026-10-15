import { apiRequest } from './apiClient';

export type PlanningCategory = 'commercial' | 'customers' | 'suppliers' | 'purchases' | 'inventory' | 'finance' | 'operational' | 'strategic' | 'other';
export type PlanningStatus = 'draft' | 'not_started' | 'in_progress' | 'on_hold' | 'completed' | 'cancelled';
export type PlanningPriority = 'low' | 'medium' | 'high' | 'urgent';
export type PlanningTaskStatus = 'pending' | 'in_progress' | 'completed';
export type PlanningEntityType = 'customer' | 'supplier' | 'product' | 'purchase' | 'order' | 'payable' | 'receivable';

export type PlanningLink = { id?: string; entity_type: PlanningEntityType; entity_id: string; label?: string };
export type PlanningTask = { id: string; planning_id: string; title: string; description?: string | null; stage?: string | null; status: PlanningTaskStatus; priority: PlanningPriority; due_date?: string | null; assignee_id?: string | null; assignee_name?: string | null; sort_order: number; observations?: string | null; completed_at?: string | null };
export type PlanningGoal = { id: string; planning_id?: string | null; name: string; description?: string | null; category: PlanningCategory; initial_value?: number | null; target_value: number; current_value: number; unit: string; start_date?: string | null; due_date?: string | null; status: 'in_progress' | 'completed' | 'cancelled'; progress_percent: number };
export type Planning = { id: string; title: string; description?: string | null; category: PlanningCategory; expected_outcome?: string | null; start_date?: string | null; due_date?: string | null; status: PlanningStatus; priority: PlanningPriority; observations?: string | null; archived: boolean; progress_percent: number; task_count: number; completed_task_count: number; tasks: PlanningTask[]; goals: PlanningGoal[]; links: PlanningLink[]; created_at: string; updated_at: string };
export type PlanningTemplate = { key: string; title: string; description: string; category: PlanningCategory; tasks: string[] };
export type PlanningOpportunity = { id: string; title: string; reason: string; category: PlanningCategory; identified_at: string; entity_type: PlanningEntityType; entity_id: string; entity_label: string };
export type TaskInput = Omit<PlanningTask, 'id' | 'planning_id' | 'assignee_name' | 'completed_at'>;
export type PlanInput = Pick<Planning, 'title' | 'description' | 'category' | 'expected_outcome' | 'start_date' | 'due_date' | 'status' | 'priority' | 'observations'> & { tasks?: Array<Partial<TaskInput> & Pick<TaskInput, 'title'>>; links?: PlanningLink[] };
export type GoalInput = Omit<PlanningGoal, 'id' | 'progress_percent'>;
export type RelatedPlanningOptions = { customers: Array<{ id: string; name: string }>; suppliers: Array<{ id: string; name: string }>; products: Array<{ id: string; name: string }>; purchases: Array<{ id: string; name: string }>; orders: Array<{ id: string; name: string }>; payables: Array<{ id: string; name: string }>; receivables: Array<{ id: string; name: string }> };

export const planningService = {
  list: (filters: { status?: string; category?: string; priority?: string; due_from?: string; due_to?: string; search?: string; include_archived?: boolean } = {}) => {
    const params = new URLSearchParams({ page_size: '500' });
    Object.entries(filters).forEach(([key, value]) => { if (value !== undefined && value !== '') params.set(key, String(value)); });
    return apiRequest<Planning[]>(`/planning?${params.toString()}`);
  },
  templates: () => apiRequest<PlanningTemplate[]>('/planning/templates'),
  opportunities: () => apiRequest<PlanningOpportunity[]>('/planning/opportunities'),
  dismissOpportunity: (productId: string) => apiRequest<void>(`/planning/opportunities/${encodeURIComponent(productId)}/dismiss`, { method: 'POST' }),
  goals: (planningId?: string) => apiRequest<PlanningGoal[]>(`/planning/goals${planningId ? `?planning_id=${encodeURIComponent(planningId)}` : ''}`),
  create: (input: PlanInput) => apiRequest<Planning>('/planning', { method: 'POST', body: JSON.stringify(input) }),
  update: (id: string, input: Partial<PlanInput> & { archived?: boolean }) => apiRequest<Planning>(`/planning/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(input) }),
  createTask: (planningId: string, input: Partial<TaskInput> & Pick<TaskInput, 'title'>) => apiRequest<PlanningTask>(`/planning/${encodeURIComponent(planningId)}/tasks`, { method: 'POST', body: JSON.stringify(input) }),
  updateTask: (id: string, input: Partial<TaskInput>) => apiRequest<PlanningTask>(`/planning/tasks/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(input) }),
  deleteTask: (id: string) => apiRequest<void>(`/planning/tasks/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  createGoal: (input: GoalInput) => apiRequest<PlanningGoal>('/planning/goals', { method: 'POST', body: JSON.stringify(input) }),
  updateGoal: (id: string, input: Partial<GoalInput>) => apiRequest<PlanningGoal>(`/planning/goals/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(input) }),
  financialLinkOptions: async () => {
    const [payables, receivables] = await Promise.all([
      apiRequest<Array<{ id: string; description: string; due_at: string; amount: number | string }>>('/finance/payables'),
      apiRequest<Array<{ id: string; description: string; due_at: string; amount: number | string }>>('/finance/receivables'),
    ]);
    const label = (item: { description: string; due_at: string; amount: number | string }) => `${item.description} · ${new Intl.DateTimeFormat('pt-BR').format(new Date(item.due_at))} · ${Number(item.amount).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}`;
    return { payables: payables.map((item) => ({ id: item.id, name: label(item) })), receivables: receivables.map((item) => ({ id: item.id, name: label(item) })) };
  },
};
