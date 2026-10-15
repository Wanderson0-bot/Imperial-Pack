import { beforeEach, describe, expect, it, vi } from 'vitest';

const { apiRequest } = vi.hoisted(() => ({ apiRequest: vi.fn() }));
vi.mock('./apiClient', () => ({ apiRequest }));

import { planningService } from './planningService';

describe('planningService', () => {
  beforeEach(() => apiRequest.mockReset());

  it('builds list filters and requests persisted plans', async () => {
    apiRequest.mockResolvedValueOnce([]);
    await planningService.list({ status: 'in_progress', category: 'inventory', search: 'estoque' });
    expect(apiRequest).toHaveBeenCalledWith(expect.stringContaining('/planning?page_size=500&status=in_progress&category=inventory&search=estoque'));
  });

  it('posts a new plan and its initial tasks through the planning API', async () => {
    const plan = { id: 'plan-1', title: 'Reposição', tasks: [{ title: 'Conferir estoque' }] };
    apiRequest.mockResolvedValueOnce(plan);
    await expect(planningService.create({ title: 'Reposição', category: 'inventory', priority: 'high', status: 'not_started', tasks: [{ title: 'Conferir estoque' }] })).resolves.toEqual(plan);
    expect(apiRequest).toHaveBeenCalledWith('/planning', expect.objectContaining({ method: 'POST', body: JSON.stringify({ title: 'Reposição', category: 'inventory', priority: 'high', status: 'not_started', tasks: [{ title: 'Conferir estoque' }] }) }));
  });

  it('propagates API failures to the page for user feedback', async () => {
    apiRequest.mockRejectedValueOnce(new Error('A API está indisponível.'));
    await expect(planningService.goals()).rejects.toThrow('A API está indisponível.');
  });
});
