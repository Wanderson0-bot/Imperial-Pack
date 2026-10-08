import { pricingConfiguration } from '../config/pricingConfig';
import type { PricingConfiguration, PricingReviewRow, Product, Purchase, RealCostBreakdown } from '../types';
import { apiRequest } from './apiClient';

const roundCurrency = (value: number): number => Number(value.toFixed(2));

type PricingReviewDto = { product_id: string; product_name: string; cost: number | string; current_price: number | string; suggested_price: number | string; minimum_price: number | string; maximum_price: number | string; margin_percent: number | string; markup_percent: number | string };

const mapReviewRow = (row: PricingReviewDto): PricingReviewRow => {
  const realCost = Number(row.cost);
  const currentPrice = Number(row.current_price);
  const currentMargin = Number(row.margin_percent);
  const currentMarkup = Number(row.markup_percent);
  const recommendedPrice = Number(row.suggested_price);
  const minimumPrice = Number(row.minimum_price);
  const maximumPrice = Number(row.maximum_price);
  const isBelowMinimumMargin = currentMargin < pricingConfiguration.minimumMargin * 100;
  const isAboveMaximumMarkup = currentMarkup > pricingConfiguration.maximumMarkup * 100;
  const situation = currentPrice <= 0
    ? 'Sem preço'
    : isBelowMinimumMargin
      ? 'Abaixo da margem mínima'
      : isAboveMaximumMarkup
        ? 'Acima do markup máximo'
        : Math.abs(currentPrice - recommendedPrice) < 0.01
          ? 'Sem alteração'
          : 'Revisar preço';

  return {
    productId: row.product_id,
    productName: row.product_name,
    realCost,
    currentPrice,
    margin: currentMargin,
    markup: currentMarkup,
    recommendedPrice,
    minimumPrice,
    maximumPrice,
    situation,
    needsReview: situation !== 'Sem alteração',
  };
};

export const pricingService = {
  getSettings: async (): Promise<PricingConfiguration> => ({ ...pricingConfiguration }),

  calculateMargin: (price: number, cost: number): number => {
    if (price <= 0) return 0;
    return roundCurrency(((price - cost) / price) * 100);
  },

  calculateMarkup: (price: number, cost: number): number => {
    if (cost <= 0) return 0;
    return roundCurrency(((price - cost) / cost) * 100);
  },

  roundCommercialPrice: (value: number, configuration: PricingConfiguration = pricingConfiguration): number => {
    if (configuration.roundingStep <= 0) return roundCurrency(value);

    const stepCount = value / configuration.roundingStep;
    const roundedStepCount = configuration.roundingMode === 'up'
      ? Math.ceil(stepCount)
      : configuration.roundingMode === 'down'
        ? Math.floor(stepCount)
        : Math.round(stepCount);

    return roundCurrency(roundedStepCount * configuration.roundingStep);
  },

  calculateRecommendedPrice: (cost: number, configuration: PricingConfiguration = pricingConfiguration): number => {
    const mathematicalPrice = cost / (1 - configuration.standardMargin);
    return pricingService.roundCommercialPrice(mathematicalPrice, configuration);
  },

  calculateRealCost: async (purchase: Purchase): Promise<RealCostBreakdown> => {
    const totalProductValue = purchase.items.reduce((sum, item) => sum + item.paidValue, 0);
    const freightShare = totalProductValue > 0 ? purchase.freight / totalProductValue : 0;
    const otherCostsShare = totalProductValue > 0 ? purchase.otherCosts / totalProductValue : 0;

    const itemCosts = purchase.items.map((item) => {
      const freightAllocation = item.paidValue * freightShare;
      const otherAllocation = item.paidValue * otherCostsShare;
      const totalCost = item.paidValue + freightAllocation + otherAllocation;
      const finalUnitCost = totalCost / item.quantity;

      return {
        productId: item.productId,
        totalProductValue: item.paidValue,
        freightShare: freightAllocation,
        otherCostShare: otherAllocation,
        totalCost,
        realUnitCost: finalUnitCost,
        finalUnitCost: roundCurrency(finalUnitCost),
      };
    });

    return {
      totalProductValue,
      freight: purchase.freight,
      otherCosts: purchase.otherCosts,
      totalCost: totalProductValue + purchase.freight + purchase.otherCosts,
      itemCosts,
    };
  },

  getRecommendedPrice: async (product: Product): Promise<number> => {
    return pricingService.calculateRecommendedPrice(product.cost);
  },

  getPriceRanges: async (product: Product): Promise<{ minimumPrice: number; recommendedPrice: number; maximumPrice: number }> => {
    const minimumPrice = product.cost / (1 - pricingConfiguration.minimumMargin);
    const recommendedPrice = pricingService.calculateRecommendedPrice(product.cost);
    const maximumPrice = product.cost * (1 + pricingConfiguration.maximumMarkup);

    return {
      minimumPrice: roundCurrency(minimumPrice),
      recommendedPrice,
      maximumPrice: roundCurrency(maximumPrice),
    };
  },

  approveRecommendedPrice: async (productId: string, approvedPrice: number): Promise<void> => {
    await apiRequest('/pricing/approve', { method: 'POST', body: JSON.stringify({ product_id: productId, new_price: approvedPrice }) });
  },

  recalculateProduct: async (productId: string): Promise<PricingReviewRow> => {
    const row = await apiRequest<PricingReviewDto>(`/pricing/products/${productId}/recalculate`, { method: 'POST' });
    return mapReviewRow(row);
  },

  getReviewRows: async (): Promise<PricingReviewRow[]> => {
    const rows = await apiRequest<PricingReviewDto[]>('/pricing/reviews');
    return rows.map(mapReviewRow);
  },
};
