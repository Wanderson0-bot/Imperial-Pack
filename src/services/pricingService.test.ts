import { describe, expect, it } from 'vitest';
import { pricingService } from './pricingService';

describe('pricing calculations', () => {
  it('calculates gross margin and markup using acquisition cost', () => {
    expect(pricingService.calculateMargin(130, 100)).toBe(23.08);
    expect(pricingService.calculateMarkup(130, 100)).toBe(30);
  });

  it('suggests the configured standard margin and commercial rounding', () => {
    expect(pricingService.calculateRecommendedPrice(100)).toBe(143);
  });

  it('allows negative target margins while keeping the maximum markup cap', async () => {
    const product = {
      id: 'test-product',
      name: 'Test product',
      category: 'General',
      description: '',
      image: '',
      unit: 'un',
      cost: 100,
      price: 90,
      margin: -11.11,
      targetMargin: -10,
      markup: -10,
      stock: 0,
      minStock: 0,
      supplier: '',
      status: 'Normal' as const,
    };

    expect(await pricingService.getRecommendedPrice(product)).toBe(91);
    await expect(pricingService.getPriceRanges(product)).resolves.toEqual({
      minimumPrice: 0,
      recommendedPrice: 91,
      maximumPrice: 200,
    });
    expect(pricingService.calculateMargin(60, 70)).toBe(-16.67);
    await expect(pricingService.getRecommendedPrice({
      ...product,
      cost: 70.24,
      targetMargin: 50,
    })).resolves.toBe(140.48);
  });
});
