import { type ReactNode } from "react";
import en from "../locales/en.json";

export type Lang = "en" | "ta";
export type Role = "owner" | "manager" | "employee";
export type Screen = "home" | "sale" | "stock" | "payments" | "reports" | "customers" | "settings";

export type IconName =
  | "shop"
  | "crown"
  | "box"
  | "hand"
  | "speaker"
  | "logout"
  | "sale"
  | "stock"
  | "wallet"
  | "chart"
  | "warning"
  | "user"
  | "search"
  | "bottle"
  | "can"
  | "plus"
  | "minus"
  | "check"
  | "back"
  | "forward"
  | "calendar"
  | "settings"
  | "receipt"
  | "phone"
  | "home"
  | "language"
  | "cash"
  | "return"
  | "print"
  | "clock"
  | "trash"
  | "edit";

export type Product = {
  id: number;
  type_id?: string;
  name: string;
  ta: string;
  price: number;
  stock: number;
  icon: IconName;
  is_returnable?: boolean;
  is_active?: boolean;
  unit?: string;
  sku?: string;
  buying_price?: number | null;
};

export type Customer = {
  id: number | string;
  name: string;
  phone: string;
  address?: string;
  balance: number;
  cans: number;
  credit_limit?: number;
  is_active?: boolean;
};

export type InvoiceItem = {
  id: number | string;
  name: string;
  variant?: string;
  unit?: string;
  sku?: string;
  ta?: string;
  quantity: number;
  price: number;
  subtotal: number;
};

export type CreatedInvoice = {
  invoice_number: string;
  customer_name: string;
  customer_phone?: string;
  customer_address?: string;
  customer_balance?: number;
  previous_balance?: number;
  items: InvoiceItem[];
  subtotal: number;
  amount_paid: number;
  cash_received?: number;
  applied_to_bill?: number;
  applied_to_old_debt?: number;
  change_returned?: number;
  balance_due: number;
  cans_returned: number;
  staff_name?: string;
  date: string;
};

export type ToastType = "success" | "error" | "info";

export type Toast = {
  id: string;
  type: ToastType;
  message: string;
};

export type AppContextValue = {
  lang: Lang;
  setLang: (lang: Lang) => void;
  voice: boolean;
  setVoice: (value: boolean) => void;
  t: (key: keyof typeof en) => string;
  speak: (enText: string, taText: string) => void;
  showToast: (message: string, type?: ToastType) => void;
};
