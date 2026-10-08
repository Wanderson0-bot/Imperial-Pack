/** Frontend API configuration. The browser only talks to FastAPI, never PostgreSQL. */
const configuredBaseUrl = (import.meta.env.VITE_API_URL ?? '').trim().replace(/\/+$/, '');

export const apiConfiguration = {
  baseUrl: configuredBaseUrl ? (configuredBaseUrl.endsWith('/api') ? configuredBaseUrl : `${configuredBaseUrl}/api`) : '',
  isConfigured: Boolean(configuredBaseUrl),
};
