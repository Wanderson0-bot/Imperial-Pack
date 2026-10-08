export type InternalPermission = 'manage_users' | 'manage_catalog' | 'manage_purchases' | 'manage_pricing' | 'manage_inventory' | 'view_reports' | 'train_intelligence';

export type InternalUser = {
  id: string;
  name: string;
  email: string;
  role: string;
  status: 'active' | 'blocked';
  permissions: InternalPermission[];
  lastAccess?: string;
  isGeneralAdmin: boolean;
};

export type InternalSession = {
  userId: string;
  createdAt: string;
};
