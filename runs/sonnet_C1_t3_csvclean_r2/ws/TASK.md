# Clean the order export

Our shop exports orders as a messy CSV (see `orders_raw.csv`). Write `clean.py` so that

    python3 clean.py INPUT.csv OUTPUT.csv

writes a clean CSV. It will be run on other exports with the same kinds of mess, so do not
hardcode anything about this particular file. Python 3.9, standard library only.

## Input
- May start with a UTF-8 BOM. Blank lines and lines whose first character is `#` are ignored.
- Header names are matched after trimming, lowercasing and turning spaces into `_`
  (so ` Order ID` → `order_id`). Columns may come in any order. Extra columns are ignored.
- Columns: `order_id, customer_email, amount, currency, order_date, status, updated_at`.
- Every value may have surrounding whitespace; trim it.

## Rules per field
- **order_id**: trimmed, uppercased. Rows with an empty order_id are dropped.
- **customer_email**: trimmed, lowercased. If it does not contain exactly one `@` with
  non-empty text on both sides, output an empty string (keep the row).
- **amount**: may contain a currency symbol (`$`, `€`, `£`) anywhere, spaces, thousands
  separators, and accounting negatives in parentheses: `(12.50)` = -12.50.
  Decimal separator rule: if both `.` and `,` appear, whichever appears **last** is the decimal
  separator and the other is a thousands separator. If only `,` appears and exactly two digits
  follow the last `,`, it is the decimal separator; otherwise `,` is a thousands separator.
  If only `.` appears it is the decimal separator.
  Output with exactly 2 decimals, rounding half away from zero (`2.005` → `2.01`).
  Rows with an empty or unparseable amount are dropped.
- **currency**: trimmed, uppercased. `$` → `USD`, `€` → `EUR`, `£` → `GBP`. If the currency
  field is empty, take it from a symbol in the amount; if there is none, use `USD`.
- **order_date**: output `YYYY-MM-DD`. Accepted inputs:
  `2026-03-04`, `2026/03/04`, `04.03.2026` (day.month.year), `03/04/2026` (month/day/year),
  `Mar 4, 2026` / `March 4, 2026`, `4 Mar 2026` / `4 March 2026` (English month names,
  any case). Single-digit day/month allowed in numeric forms. Rows with a missing or invalid
  date (e.g. `2026-02-30`) are dropped.
- **status**: trimmed, lowercased; `canceled` → `cancelled`. Allowed: `pending, paid, shipped,
  cancelled, refunded`. Anything else becomes `unknown`.
- **updated_at**: `YYYY-MM-DDTHH:MM:SS` optionally followed by `Z`, or the same with a space
  instead of `T`. Only used for de-duplication; not in the output. Empty = oldest possible.

## De-duplication
Rows with the same (normalised) order_id: keep only the one with the latest `updated_at`.
On a tie, keep the one that appears later in the file. Dropped rows (bad amount/date/id) never
take part in de-duplication.

## Output
Header `order_id,customer_email,amount,currency,order_date,status`, then rows sorted by
`order_date`, then `order_id`. Standard `csv` module quoting, `\n` line endings.
