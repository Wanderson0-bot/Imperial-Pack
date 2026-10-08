export type NavigationItem = {
  label: string;
  to: string;
  icon: string;
};

export type PageHeaderProps = {
  title: string;
  description?: string;
  actions?: React.ReactNode;
};

export type Metric = {
  label: string;
  value: string;
  trend?: string;
  tone?: 'positive' | 'neutral' | 'warning' | 'critical';
};

export type ProductCategory = string;

export type Category = {
  id: string;
  name: string;
  image: string;
  isOfficial?: boolean;
};

export type ProductStatus = 'Normal' | 'Baixo' | 'Crítico' | 'Sem estoque';

export type Product = {
  id: string;
  name: string;
  category: ProductCategory;
  description: string;
  image: string;
  unit: string;
  cost: number;
  price: number;
  margin: number;
  markup: number;
  stock: number;
  minStock: number;
  supplier: string;
  status: ProductStatus;
};

export type CostHistoryEntry = {
  id: string;
  productId: string;
  date: string;
  previousCost: number;
  newCost: number;
  reason: string;
  supplier: string;
};

export type PriceHistoryEntry = {
  id: string;
  productId: string;
  date: string;
  previousPrice: number;
  newPrice: number;
  reason: string;
  margin: number;
};

export type Supplier = {
  id: string;
  name: string;
  email?: string | null;
  phone?: string | null;
  location?: string | null;
  minimumOrder?: number | null;
  deliveryDays?: number | null;
  contact: string;
  products: string[];
  productIds?: string[];
  productCosts?: Array<{ id: string; name: string; lastCost: number | null; lastPurchase: string | null }>;
  lastCost: number;
  history: number;
  lastPurchase: string;
  observations: string;
};

export type PurchaseItem = {
  id: string;
  productId: string;
  quantity: number;
  paidValue: number;
  unitCost: number;
  discount: number;
  description?: string;
  freightShare: number;
  otherCostShare: number;
  realUnitCost: number;
  totalCost: number;
};

export type Purchase = {
  id: string;
  supplier: string;
  date: string;
  documentNumber?: string;
  observations?: string;
  productsValue: number;
  discountTotal: number;
  totalValue: number;
  freight: number;
  otherCosts: number;
  items: PurchaseItem[];
  status: 'registrada' | 'em revisão' | 'aprovada';
};

export type PurchaseDraftItem = {
  productId: string;
  quantity: number;
  unitCost: number;
  discount: number;
  description?: string;
};

export type PurchaseDraft = {
  supplierId: string;
  date: string;
  documentNumber?: string;
  freight: number;
  otherCosts: number;
  observations?: string;
  items: PurchaseDraftItem[];
};

export type RealCostBreakdown = {
  totalProductValue: number;
  freight: number;
  otherCosts: number;
  totalCost: number;
  itemCosts: Array<{
    productId: string;
    totalProductValue: number;
    freightShare: number;
    otherCostShare: number;
    totalCost: number;
    realUnitCost: number;
    finalUnitCost: number;
  }>;
};

export type PricingReviewRow = {
  productId: string;
  productName: string;
  realCost: number;
  currentPrice: number;
  margin: number;
  markup: number;
  recommendedPrice: number;
  minimumPrice: number;
  maximumPrice: number;
  situation: string;
  needsReview: boolean;
};

export type Customer = {
  id: string;
  name: string;
  company: string;
  phone: string;
  email?: string | null;
  city?: string | null;
  notes?: string | null;
  address?: CustomerAddress | null;
  externalId?: string | null;
  status?: string;
  orders?: number;
  totalSpent?: number;
  averageTicket?: number;
  lastPurchase?: string | null;
  origin?: 'internal' | 'future-public-site';
};

export type CustomerAddress = {
  id?: string;
  label: string;
  street?: string | null;
  number?: string | null;
  complement?: string | null;
  district?: string | null;
  city?: string | null;
  state?: string | null;
  postal_code?: string | null;
};

export type PartnerReplenishmentCycle = 'weekly' | 'fortnightly' | 'monthly' | 'bimonthly' | 'custom';
export type PartnerCondition = {
  discountPercent?: number;
  paymentTermDays?: number;
  paymentMethod?: string;
  creditLimit?: number;
  servicePriority?: 'standard' | 'priority';
  notes?: string;
};
export type PartnerProfile = {
  customerId: string;
  partnerId?: string;
  status: 'active' | 'inactive';
  cycle?: PartnerReplenishmentCycle;
  customCycleDays?: number;
  minimumOrderValue?: number;
  conditions?: PartnerCondition;
  activatedAt: string;
};
export type PartnerPurchaseRecord = {
  customerId: string;
  productId: string;
  quantity: number;
  purchasedAt: string;
  unitPrice: number;
  unitCost?: number;
  orderId: string;
  source: 'internal' | 'whatsapp' | 'salesperson' | 'future-public-site';
  intervalSincePreviousDays?: number;
};
export type OrderLineItem = {
  productId: string;
  quantity: number;
  unitPrice: number;
  unitCost?: number;
};
export type ReplenishmentPrediction = {
  customerId: string;
  productId: string;
  predictedConsumption?: number;
  replenishmentWindow?: { start: string; end: string };
  depletionWindow?: { start: string; end: string };
  recommendedQuantity?: number;
  trend?: 'increasing' | 'stable' | 'decreasing' | 'unknown';
  confidence: 'high' | 'medium' | 'low' | 'insufficient-data';
  modelVersion?: string;
  generatedAt?: string;
  explanation?: string;
};
export type PredictionResult = {
  predictionId: string;
  customerId: string;
  productId: string;
  predictedFor: string;
  actualReplenishmentAt?: string;
  actualQuantity?: number;
  recordedAt: string;
};

export type OrderStatus = 'Novo' | 'Confirmado' | 'Em separação' | 'Pronto' | 'Entregue' | 'Cancelado';

export type Order = {
  id: string;
  customer: string;
  value: number;
  status: OrderStatus;
  date: string;
  items: number;
  customerId?: string;
  lineItems?: OrderLineItem[];
  source?: PartnerPurchaseRecord['source'];
};

export type InventoryMovement = {
  id: string;
  productId: string;
  type: 'entrada' | 'saída' | 'ajuste';
  quantity: number;
  date: string;
  reason: string;
};

export type PricingRoundingMode = 'nearest' | 'up' | 'down';

export type PricingConfiguration = {
  minimumMargin: number;
  standardMargin: number;
  maximumMarkup: number;
  roundingMode: PricingRoundingMode;
  roundingStep: number;
};

export type PricingSettings = PricingConfiguration;

export type AlertType = 'info' | 'warning' | 'success' | 'danger';

export type Alert = {
  id: string;
  type: AlertType;
  title: string;
  message: string;
};

export type IntelligenceInsight = {
  id: string;
  category: 'Demanda' | 'Estoque' | 'Clientes' | 'Oportunidades';
  title: string;
  detail: string;
  impact: 'alto' | 'médio' | 'baixo';
};

export type User = {
  id: string;
  name: string;
  role: string;
  permissions: string[];
};

export type CompanySettings = {
  minimumMargin: number;
  defaultMargin: number;
  maxMarkup: number;
  rounding: number;
  minimumStock: number;
  lowStockThreshold: number;
};
