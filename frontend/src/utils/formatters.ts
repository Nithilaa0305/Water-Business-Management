/**
 * Shared currency and number formatters for Wholesale Billing System.
 * Adheres strictly to the standard: "Rs. " prefix followed by space in both English and Tamil.
 * Examples: Rs. 0, Rs. 1,700, Rs. 1,700.50, -Rs. 300
 * Whole amounts without ".00"; fractional amounts to two decimal places.
 */

export function formatMoney(amount: number | string | null | undefined): string {
  if (amount === null || amount === undefined || amount === "") {
    return "Rs. 0";
  }
  const num = Number(amount);
  if (isNaN(num)) {
    return "Rs. 0";
  }
  const isNegative = num < 0;
  const abs = Math.abs(num);
  const isWhole = Number.isInteger(abs);
  const formattedNumber = abs.toLocaleString("en-IN", {
    minimumFractionDigits: isWhole ? 0 : 2,
    maximumFractionDigits: 2,
  });
  return isNegative ? `-Rs. ${formattedNumber}` : `Rs. ${formattedNumber}`;
}
