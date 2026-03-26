import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

DATA_ROOT = Path(__file__).resolve().parent.parent / 'sap-o2c-data'
DB_PATH   = Path(__file__).resolve().parent / 'o2c.db'

# Primary key definitions per table
TABLE_PKS: Dict[str, List[str]] = {
    'sales_order_headers':                    ['salesOrder'],
    'sales_order_items':                      ['salesOrder', 'salesOrderItem'],
    'outbound_delivery_headers':              ['deliveryDocument'],
    'outbound_delivery_items':                ['deliveryDocument', 'deliveryDocumentItem'],
    'billing_document_headers':               ['billingDocument'],
    'billing_document_items':                 ['billingDocument', 'billingDocumentItem'],
    'billing_document_cancellations':         ['billingDocument'],
    'journal_entry_items_accounts_receivable':['accountingDocument', 'accountingDocumentItem'],
    'payments_accounts_receivable':           ['accountingDocument', 'accountingDocumentItem'],
    'business_partners':                      ['businessPartner'],
    'product_descriptions':                   ['material', 'language'],
    'product_plants':                         ['material', 'plant'],
    'product_storage_locations':              ['material', 'plant', 'storageLocation'],
    'products':                               ['material'],
    'plants':                                 ['plant'],
    'customer_company_assignments':           ['businessPartner', 'companyCode'],
    'customer_sales_area_assignments':        ['businessPartner', 'salesOrganization',
                                               'distributionChannel', 'division'],
    'business_partner_addresses':             ['businessPartner', 'addressID'],
}


def detect_sqlite_type(value: Any) -> str:
    if value is None:
        return 'TEXT'
    if isinstance(value, bool):
        return 'INTEGER'
    if isinstance(value, int):
        return 'INTEGER'
    if isinstance(value, float):
        return 'REAL'
    return 'TEXT'


def normalize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float)):
        return value
    if isinstance(value, bool):
        return int(value)
    return json.dumps(value, default=str)


def read_jsonl_file(filepath: Path) -> List[Dict]:
    rows = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"  ⚠ Bad JSON in {filepath.name}: {e}")
    return rows


def create_table(conn: sqlite3.Connection, table_name: str, sample_row: Dict):
    """Create table with column types inferred from sample row + UNIQUE constraint for dedup."""
    col_defs = []
    for col, val in sample_row.items():
        col_type = detect_sqlite_type(val)
        col_defs.append(f'"{col}" {col_type}')

    pks = TABLE_PKS.get(table_name, [])
    if pks:
        pk_cols = ', '.join(f'"{c}"' for c in pks)
        col_defs.append(f'UNIQUE ({pk_cols})')

    create_stmt = (
        f'CREATE TABLE IF NOT EXISTS "{table_name}" '
        f'({", ".join(col_defs)})'
    )
    conn.execute(create_stmt)


def ingest_table(conn: sqlite3.Connection, table_name: str, data: List[Dict]) -> int:
    if not data:
        return 0

    columns = list(data[0].keys())
    col_names   = ', '.join(f'"{c}"' for c in columns)
    placeholders = ', '.join('?' for _ in columns)
    insert_stmt = (
        f'INSERT OR IGNORE INTO "{table_name}" '
        f'({col_names}) VALUES ({placeholders})'
    )

    inserted = 0
    for row in data:
        values = [normalize_value(row.get(col)) for col in columns]
        try:
            conn.execute(insert_stmt, values)
            inserted += 1
        except sqlite3.Error:
            pass
    return inserted


def build_db():
    if DB_PATH.exists():
        DB_PATH.unlink()
        print(f"Removed old {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")

    total_tables = 0
    total_rows   = 0

    try:
        for folder in sorted(DATA_ROOT.iterdir()):
            if not folder.is_dir():
                continue

            table_name  = folder.name
            jsonl_files = sorted(folder.glob('*.jsonl'))
            if not jsonl_files:
                continue

            # Get schema from first non-empty file
            first_sample = None
            for fn in jsonl_files:
                rows = read_jsonl_file(fn)
                if rows:
                    first_sample = rows[0]
                    break
            if not first_sample:
                continue

            create_table(conn, table_name, first_sample)

            table_rows = 0
            for fn in jsonl_files:
                rows = read_jsonl_file(fn)
                table_rows += ingest_table(conn, table_name, rows)

            conn.commit()
            total_tables += 1
            total_rows   += table_rows
            print(f"  ✅ [{table_name}] → {table_rows:,} rows")

    finally:
        conn.close()

    print(f"\n🎉 Ingestion complete: {total_tables} tables, {total_rows:,} total rows → {DB_PATH}")


if __name__ == '__main__':
    build_db()
