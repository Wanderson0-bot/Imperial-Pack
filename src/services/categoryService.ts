import type { Category } from '../types';
import { apiRequest } from './apiClient';

type CategoryDto = {
  id: string;
  name: string;
  image_url?: string | null;
};

export const categoryService = {
  getAll: async (): Promise<Category[]> =>
    (
      await apiRequest<CategoryDto[]>('/products/categories')
    ).map((row) => ({
      id: row.id,
      name: row.name,
      image: row.image_url ?? '',
      isOfficial: false,
    })),

  create: async (input: Omit<Category, 'id'>): Promise<Category> => {
    const result = await apiRequest<CategoryDto>('/products/categories', {
      method: 'POST',
      body: JSON.stringify({
        name: input.name,
        image_url: input.image,
      }),
    });

    return {
      id: result.id,
      name: result.name,
      image: result.image_url ?? '',
      isOfficial: false,
    };
  },

  update: async (category: Category): Promise<Category> => {
    const result = await apiRequest<CategoryDto>(
      `/products/categories/${category.id}`,
      {
        method: 'PATCH',
        body: JSON.stringify({
          name: category.name,
          image_url: category.image,
        }),
      },
    );

    return {
      id: result.id,
      name: result.name,
      image: result.image_url ?? '',
      isOfficial: false,
    };
  },

  remove: async (
    id: string,
    replacementCategory?: string,
  ): Promise<void> => {
    let query = '';

    if (replacementCategory) {
      const replacement = (await categoryService.getAll()).find(
        (item) => item.name === replacementCategory,
      );

      if (!replacement) {
        throw new Error('Replacement category not found.');
      }

      query = `?replacement_category_id=${encodeURIComponent(
        replacement.id,
      )}`;
    }

    await apiRequest(`/products/categories/${id}${query}`, {
      method: 'DELETE',
    });
  },
};