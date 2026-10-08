import type { Customer } from '../types';
import { apiRequest } from './apiClient';

export type CustomerInput = {
  name: string;
  company?: string;
  email?: string;
  phone?: string;
  city?: string;
  notes?: string;
  externalId?: string;
  address?: Omit<NonNullable<Customer['address']>, 'id'>;
};

type CustomerDto = {
  id: string;
  name: string;
  establishment: string | null;
  phone: string | null;
  email: string | null;
  city: string | null;
  notes: string | null;
  external_id: string | null;
  status: string;
  origin: string;
  address: Customer['address'];
  orders?: number | null;
  total_spent?: number | string | null;
  average_ticket?: number | string | null;
  last_purchase?: string | null;
};

const mapCustomer = (customer: CustomerDto): Customer => ({
  id: customer.id,
  name: customer.name,
  company: customer.establishment ?? '',
  phone: customer.phone ?? '',
  email: customer.email,
  city: customer.city,
  notes: customer.notes,
  externalId: customer.external_id,
  address: customer.address,
  status: customer.status,
  orders: customer.orders ?? undefined,
  totalSpent: customer.total_spent == null ? undefined : Number(customer.total_spent),
  averageTicket: customer.average_ticket == null ? undefined : Number(customer.average_ticket),
  lastPurchase: customer.last_purchase?.slice(0, 10) ?? null,
  origin: customer.origin === 'SITE_PUBLICO' ? 'future-public-site' : 'internal',
});

export const customerService = {
  getAll: async (search?: string): Promise<Customer[]> => {
    const query = search?.trim() ? `?search=${encodeURIComponent(search.trim())}` : '';
    return (await apiRequest<CustomerDto[]>(`/customers${query}`)).map(mapCustomer);
  },
  create: async (input: CustomerInput): Promise<Customer> => mapCustomer(await apiRequest<CustomerDto>('/customers', { method: 'POST', body: JSON.stringify({ name: input.name, establishment: input.company || null, email: input.email || null, phone: input.phone || null, city: input.city || null, notes: input.notes || null, external_id: input.externalId || null, address: input.address ?? null, origin: 'INTERNAL' }) })),
  update: async (id: string, input: CustomerInput): Promise<Customer> => mapCustomer(await apiRequest<CustomerDto>(`/customers/${id}`, { method: 'PATCH', body: JSON.stringify({ name: input.name, establishment: input.company || null, email: input.email || null, phone: input.phone || null, city: input.city || null, notes: input.notes || null, address: input.address ?? null }) })),
};
