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
});
