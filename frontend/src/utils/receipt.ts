import type { CreatedInvoice } from "../types";

type SavedReceipt = Omit<CreatedInvoice, "items"> & {
  items: (Omit<CreatedInvoice["items"][number], "id"> & { sale_item_id: string })[];
};

// Both checkout and history render these persisted values, not the local cart.
export function toInvoice(receipt: SavedReceipt): CreatedInvoice {
  if (!receipt?.invoice_number || !Array.isArray(receipt.items) || !receipt.items.length) {
    throw new Error("Saved invoice details are missing. Open Invoice History to retry.");
  }
  return { ...receipt, items: receipt.items.map((item) => ({ ...item, id: item.sale_item_id })) };
}
