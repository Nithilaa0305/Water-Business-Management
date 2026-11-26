# Water Business Manager - User Manual

## 1. Overview
**Water Business Manager** is an offline Windows desktop billing, inventory, customer credit, and refill management application specifically designed for bottled drinking water wholesale and distribution operations in Sri Lanka.

## 2. Key Modules & Daily Operations

### 2.1 First-Time Setup
When launching the application for the first time, a simple wizard prompts for:
- Business name and address
- Contact telephone and email
- Owner 4-digit PIN for secure authentication
- Language preference (English or Tamil)
- Invoice numbering prefix (e.g. `INV-`)

The 5 default water products (`W0500`, `W1000`, `W1500`, `W5000`, and `W19000`) are created automatically.

### 2.2 Fast Billing & Sales
The Billing screen is designed for high-speed operation:
1. **Customer Selection**: Search by Customer ID (e.g. `CUST-001`), Name, or Phone, or click `🚶 Walk-in Cash` for quick anonymous cash sales.
2. **Pre-Set Agreed Pricing & Suggestions**: 
   - When a customer is selected, the system automatically checks for custom prices agreed with that customer in advance.
   - If an agreed rate exists, the price field is populated automatically with a green `🏷 Agreed Price (Pre-Set)` badge.
   - You can also click `💲 Pre-Set Prices` directly on the billing screen to view or configure customer contract prices without leaving the bill.
3. **On-the-Fly Price Flexibility**:
   - Change the price before adding, OR edit the **Unit Price** or **Qty** directly inside the bill items table at any time.
   - Check `💾 Update customer's agreed prices with the unit prices on this bill` to permanently save the new prices as that customer's pre-set rate for future bills.
4. **Product & Packaging Unit**: Select product and packaging unit (individual bottle, case of 12 / 24). Real-time available stock is displayed.
5. **19 L Reusable Bottle Exchange**: Enter empty bottles returned. Customer bottle balance is updated instantly.
6. **Payment Method**: Select Cash, Credit, Bank Transfer, or Mixed. Overpayments automatically create advance credits.
7. **Save & Print**: Click **Save Bill** or **Save & Print** to generate thermal receipts or A4 invoices.

### 2.3 Special 19 L Returnable Bottle Management
19 L polycarbonate water bottles are reusable containers tracked separately from the water product:
- **Bottle Delivery**: Increases customer bottle obligation; decreases warehouse full stock.
- **Bottle Exchange**: Customer receives full bottles and returns empty bottles. The net difference updates their obligation.
- **Empty Return Without Purchase**: Use **Return Empty Bottles** to receive empty containers without charging or selling water.
- **Refill Operation**: Refill warehouse empty bottles into full inventory. Enter direct costs (water treatment, caps, labour). The system calculates the unit refill cost and creates a new FIFO inventory batch.

### 2.4 Customer Credit & Payments
- View accounts receivable and overdue aging brackets (Current, 1–30, 31–60, >60 days).
- Record payments easily using **Receive Payment**. Payments are automatically applied to the oldest unpaid invoice, or you can manually allocate to specific bills.
- Any excess payment is securely held as a customer advance.

### 2.5 Stock Management
- Traceable batch-based inventory: view remaining quantity, unit buying cost, and batch status.
- Adjust stock with mandatory reasons (Damage, Breakage, Expiration, Lost bottles, or Count corrections).

### 2.6 Backups & Data Safety
- Your database is securely stored at `%LOCALAPPDATA%\WaterBusinessManager\data\business.db`.
- Create verified online backups at any time via **Settings & Backup**.
- Backups can be restored safely with an automatic pre-restore safety snapshot.
