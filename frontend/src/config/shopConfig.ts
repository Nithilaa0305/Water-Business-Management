// Authoritative Shop Configuration
// Reads from Vite environment variables when configured, avoiding placeholder/mock contacts or fake tax IDs.

export interface ShopConfig {
  name: string;
  nameTa: string;
  tagline?: string;
  taglineTa?: string;
  address?: string;
  addressTa?: string;
  phone?: string;
  email?: string;
  taxNumber?: string;
}

export const shopConfig: ShopConfig = {
  name: import.meta.env.VITE_SHOP_NAME || "Namma Wholesale Distributors",
  nameTa: import.meta.env.VITE_SHOP_NAME_TA || "நம்ம மொத்த வியாபாரம்",
  tagline: import.meta.env.VITE_SHOP_TAGLINE || "Wholesale Billing & Inventory",
  taglineTa: import.meta.env.VITE_SHOP_TAGLINE_TA || "மொத்த விற்பனை & இருப்பு மேலாண்மை",
  address: import.meta.env.VITE_SHOP_ADDRESS || "",
  addressTa: import.meta.env.VITE_SHOP_ADDRESS_TA || "",
  phone: import.meta.env.VITE_SHOP_PHONE || "",
  email: import.meta.env.VITE_SHOP_EMAIL || "",
  taxNumber: import.meta.env.VITE_SHOP_TAX_NUMBER || "",
};
