import type { InternalPermission, InternalUser } from '../types/auth';
import { apiConfiguration } from '../config/api';
import { apiRequest } from './apiClient';

type ApiUser = { id: string; name: string; email: string; role: string; permissions: string[]; is_general_admin: boolean };
let cachedUser: InternalUser | null = null;

const mapPermission = (key: string): InternalPermission | undefined => key.startsWith('users:') ? 'manage_users'
  : key.startsWith('products:') ? 'manage_catalog'
  : key.startsWith('purchases:') ? 'manage_purchases'
  : key.startsWith('pricing:') ? 'manage_pricing'
  : key.startsWith('inventory:') ? 'manage_inventory'
  : key === 'intelligence:train' ? 'train_intelligence'
  : key === 'reports:read' ? 'view_reports' : undefined;

const mapUser = (user: ApiUser): InternalUser => ({
  id: user.id, name: user.name, email: user.email, role: user.role, status: 'active',
  permissions: user.permissions.map(mapPermission).filter((permission): permission is InternalPermission => Boolean(permission)),
  isGeneralAdmin: user.is_general_admin,
});

export const authService = {
  isConfiguredForBackend: apiConfiguration.isConfigured,
  getCurrentUser: (): InternalUser | null => cachedUser,
  getCurrentUserAsync: async (): Promise<InternalUser | null> => {
    if (!apiConfiguration.isConfigured) return null;
    try {
      const apiUser = await apiRequest<ApiUser>('/auth/me');
      cachedUser = mapUser(apiUser);
      return cachedUser;
    } catch (error) {
      cachedUser = null;
      return null;
    }
  },
  signIn: async (email: string, password: string): Promise<InternalUser> => {
    await apiRequest('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) });
    const user = await authService.getCurrentUserAsync();
    if (!user) throw new Error('Não foi possível carregar a sessão autenticada.');
    return user;
  },
  registerInitialAdmin: async (name: string, email: string, password: string): Promise<void> => {
    await apiRequest('/auth/register', { method: 'POST', body: JSON.stringify({ name, email, password }) });
  },
  signOut: async (): Promise<void> => {
    try { if (apiConfiguration.isConfigured) await apiRequest('/auth/logout', { method: 'POST' }); }
    finally { cachedUser = null; }
  },
  getUsers: async (): Promise<InternalUser[]> => {
    const users = await apiRequest<Array<{ id: string; name: string; email: string; role_id: string; is_active: boolean; is_general_admin: boolean }>>('/users');
    return users.map((user) => ({ id: user.id, name: user.name, email: user.email, role: user.role_id, status: user.is_active ? 'active' : 'blocked', permissions: [], isGeneralAdmin: user.is_general_admin }));
  },
  getRoles: async (): Promise<Array<{ id: string; name: string }>> => {
    return apiRequest('/users/roles');
  },
  createRole: async (input: { name: string; description?: string; permissions: string[] }) => {
    if (!apiConfiguration.isConfigured) throw new Error('API de funções não configurada.');
    return apiRequest('/users/roles', { method: 'POST', body: JSON.stringify(input) });
  },
  createUser: async (input: { name: string; email: string; password: string; role_id: string }) => {
    if (!apiConfiguration.isConfigured) throw new Error('API de usuários não configurada.');
    return apiRequest('/users', { method: 'POST', body: JSON.stringify(input) });
  },
  updateUserStatus: async (id: string, is_active: boolean) => {
    if (!apiConfiguration.isConfigured) throw new Error('API de usuários não configurada.');
    return apiRequest(`/users/${id}`, { method: 'PATCH', body: JSON.stringify({ is_active }) });
  },
  deleteUser: async (id: string) => {
    if (!apiConfiguration.isConfigured) throw new Error('API de usuários não configurada.');
    return apiRequest<void>(`/users/${id}`, { method: 'DELETE' });
  },
  can: (permission: InternalPermission) => Boolean(cachedUser?.isGeneralAdmin || cachedUser?.permissions.includes(permission)),
};
