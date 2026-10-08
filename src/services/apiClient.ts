import { apiConfiguration } from '../config/api';

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
    this.name = 'ApiError';
  }
}

/** Shared FastAPI transport boundary. */
export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  if (!apiConfiguration.isConfigured) throw new Error('Conexão com o backend indisponível. Configure VITE_API_URL.');
  const response = await fetch(`${apiConfiguration.baseUrl}${path}`, {
    ...init,
    credentials: 'include',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json', ...init?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: unknown } | null;
    const message = typeof body?.detail === 'string' ? body.detail : `A API retornou HTTP ${response.status}.`;
    throw new ApiError(message, response.status);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
