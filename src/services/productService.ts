import type { CostHistoryEntry, PriceHistoryEntry, Product } from '../types';
import { apiRequest } from './apiClient';

type ProductDto = { id: string; name: string; category_id?: string | null; image_url?: string | null; description?: string | null; unit: string; current_cost: number | string; current_price: number | string; margin_percent: number | string; markup_percent: number | string; stock: number | string; minimum_stock: number | string; status: Product['status'] };
const mapProduct = (row: ProductDto): Product => ({ id: row.id, name: row.name, category: row.category_id ?? 'Sem categoria', description: row.description ?? '', image: row.image_url ?? '', unit: row.unit, cost: Number(row.current_cost), price: Number(row.current_price), margin: Number(row.margin_percent), markup: Number(row.markup_percent), stock: Number(row.stock), minStock: Number(row.minimum_stock), supplier: '', status: row.status });
const categoryId = async (name: string): Promise<string | undefined> => {
  const categories = await apiRequest<Array<{ id: string; name: string }>>('/products/categories');
  return categories.find((category) => category.name === name)?.id;
};
const mapProductDto = async (row: ProductDto): Promise<Product> => {
  const categories = await apiRequest<Array<{ id: string; name: string }>>('/products/categories');
  return mapProduct({ ...row, category_id: categories.find((category) => category.id === row.category_id)?.name ?? row.category_id });
};

export const productService = {
  getAll: async (): Promise<Product[]> => Promise.all((await apiRequest<ProductDto[]>('/products')).map(mapProductDto)),
  getById: async (id: string): Promise<Product | undefined> => {
    return (await productService.getAll()).find((product) => product.id === id);
  },
  getByCategory: async (category: string): Promise<Product[]> => {
    return (await productService.getAll()).filter((product) => product.category === category);
  },
  getCostHistory: async (productId: string): Promise<CostHistoryEntry[]> => {
    const rows = await apiRequest<Array<{ id: string; product_id: string; date: string; previous_cost: number | string; new_cost: number | string; reason: string; supplier: string }>>(`/products/${productId}/cost-history`);
    return rows.map((row) => ({ id: row.id, productId: row.product_id, date: row.date.slice(0, 10), previousCost: Number(row.previous_cost), newCost: Number(row.new_cost), reason: row.reason, supplier: row.supplier }));
  },
  getPriceHistory: async (productId: string): Promise<PriceHistoryEntry[]> => {
    const rows = await apiRequest<Array<{ id: string; product_id: string; date: string; previous_price: number | string; new_price: number | string; reason: string; margin: number | string }>>(`/products/${productId}/price-history`);
    return rows.map((row) => ({ id: row.id, productId: row.product_id, date: row.date.slice(0, 10), previousPrice: Number(row.previous_price), newPrice: Number(row.new_price), reason: row.reason, margin: Number(row.margin) }));
  },
  updateProduct: async (product: Product): Promise<Product> => {
    const id = await categoryId(product.category);
    const row = await apiRequest<ProductDto>(`/products/${product.id}`, { method: 'PATCH', body: JSON.stringify({ name: product.name, category_id: id, image_url: product.image, description: product.description, unit: product.unit, current_price: product.price, minimum_stock: product.minStock }) });
    return mapProductDto(row);
  },
  create: async (product: Product): Promise<Product> => {
    const id = await categoryId(product.category);
    const row = await apiRequest<ProductDto>('/products', { method: 'POST', body: JSON.stringify({ name: product.name, category_id: id, image_url: product.image, description: product.description, unit: product.unit, current_cost: product.cost, current_price: product.price, minimum_stock: product.minStock }) });
    return mapProductDto(row);
  },
  remove: async (id: string): Promise<void> => {
    await apiRequest(`/products/${id}`, { method: 'DELETE' });
  },
};
