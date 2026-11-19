import type { Product, Customer } from "../types";

export function classifyProductRank(p: Partial<Product>): number {
  const n = (p.name || "").toLowerCase();
  const isRet = Boolean(p.is_returnable);
  // Empty cans / returnable container inventory (rank 6)
  if (n.includes("empty") || (isRet && (n.includes("bottle") || n.includes("can")) && !n.includes("filled") && !n.includes("water"))) {
    return 6;
  }
  // 1. 500 ml
  if (n.includes("500") && n.includes("ml")) return 1;
  // 2. 1 L
  if ((n.includes("1 l") || n.includes("1l")) && !n.includes("1.5") && !n.includes("19") && !n.includes("20")) return 2;
  // 3. 1.5 L
  if (n.includes("1.5")) return 3;
  // 4. 5 L
  if (n.includes("5") && (n.includes("l") || n.includes("liter")) && !n.includes("500") && !n.includes("1.5")) return 4;
  // 5. 19 L or 20 L filled water
  if (n.includes("19") || (n.includes("20") && (n.includes("water") || n.includes("can")))) return 5;
  // 10. Other regular products
  return 10;
}

export function getProductVolumeRank(p: Partial<Product>): number {
  return classifyProductRank(p);
}

export const sampleProducts: Product[] = [
  { id: 1, type_id: "c069af1d-343f-49f6-9227-435420c6794a", name: "500 ml Water", ta: "500மிலி தண்ணீர்", price: 22, stock: 142, icon: "bottle" },
  { id: 2, type_id: "56c143b4-c953-47bf-8793-946411a0670d", name: "1 L Water", ta: "1 லிட்டர் தண்ணீர்", price: 35, stock: 92, icon: "bottle" },
  { id: 3, type_id: "73527546-c05a-400e-a785-381f3f02ab65", name: "1.5 L Water", ta: "1.5 லிட்டர் தண்ணீர்", price: 50, stock: 78, icon: "bottle" },
  { id: 4, type_id: "60447a66-82c3-4a56-825b-4e0b998b9573", name: "5 L Water", ta: "5 லிட்டர் தண்ணீர்", price: 120, stock: 60, icon: "can" },
  { id: 5, type_id: "ca12b690-92a6-49d3-bd75-b3d8f67562df", name: "19 L Water (filled)", ta: "19 லிட்டர் கேன்", price: 90, stock: 125, icon: "can" },
  { id: 6, type_id: "3485449f-4525-4d11-a914-d807377a5320", name: "19 L Bottle (empty/new)", ta: "19 லிட்டர் காலி கேன் (புதியது)", price: 150, stock: 50, icon: "can", is_returnable: true },
];

export const sampleCustomers: Customer[] = [
  { id: "b0cd1e65-1194-4115-a804-ffd792d1736f", name: "Nimal Stores", phone: "077-1111111", balance: 5020, cans: 25 },
  { id: "aa19fda6-a12a-4675-b3fb-948070f5a710", name: "Kamal Hotel", phone: "071-2222222", balance: 4800, cans: 0 },
  { id: "c18a2091-7661-4235-8664-9f20e4eb5350", name: "Murugan Stores", phone: "98420 11224", balance: 12400, cans: 5 },
];
