import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Any

DATA_ROOT = Path(__file__).resolve().parent.parent / 'sap-o2c-data'
DB_PATH = Path(__file__).resolve().parent / 'o2c.db'

TABLES = {
    'sales_order_headers': {'pk': ['salesOrder']},
    'sales_order_items': {'pk': ['salesOrder', 'salesOrderItem']},
    'outbound_delivery_headers': {'pk': ['deliveryDocument']},
    'outbound_delivery_items': {'pk': ['deliveryDocument', 'deliveryDocumentItem']},
    'billing_document_headers': {'pk': ['billingDocument']},
    'billing_document_items': {'pk': ['billingDocument', 'billingDocumentItem']},
    'journal_entry_items_accounts_receivable': {'pk': ['accountingDocument', 'accountingDocumentItem']},
    'payments_accounts_receivable': {'pk': ['accountingDocument', 'accountingDocumentItem']},
    'business_partners': {'pk': ['businessPartner']},
    'product_descriptions': {'pk': ['material']},
    'product_plants': {'pk': ['material', 'plant']},
    'product_storage_locations': {'pk': ['material', 'storageLocation']},
    'plants': {'pk': ['plant']},
    'customer_company_assignments': {'pk': ['soldToParty', 'companyCode']},
    'customer_sales_area_assignments': {'pk': ['soldToParty', 'salesOrganization', 'distributionChannel', 'organizationDivision']},
    'business_partner_addresses': {'pk': ['businessPartner', 'addressID']}
}


def detect_sqlite_type(value: Any) -> str:
    if value is None:
        return 'TEXT'
    if isinstance(value, bool):
        return 'INTEGER'  # SQLite stores bool as int
    if isinstance(value, int):
        return 'INTEGER'
    if isinstance(value, float):
        return 'REAL'
    return 'TEXT'


def normalize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, bool, int, float)):
        return value
    return json.dumps(value, default=str)


def read_jsonl_file(filepath: Path) -> List[Dict]:
    rows = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def create_table(conn: sqlite3.Connection, table_name: str, sample_row: Dict):
    columns = []
    for col, val in sample_row.items():
        col_type = detect_sqlite_type(val)
        columns.append(f'"{col}" {col_type}')

    create_stmt = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({", ".join(columns)})'
    conn.execute(create_stmt)


def ingest_table(conn: sqlite3.Connection, table_name: str, data: List[Dict]):
    if not data:
        return

    columns = list(data[0].keys())
    placeholders = ', '.join('?' for _ in columns)
    insert_stmt = f'INSERT OR IGNORE INTO "{table_name}" ({", ".join(f'"{c}"' for c in columns)}) VALUES ({placeholders})'

    for row in data:
        values = [normalize_value(row.get(col)) for col in columns]
        conn.execute(insert_stmt, values)


def build_db():
    conn = sqlite3.connect(DB_PATH)
    try:
        for folder in sorted(DATA_ROOT.iterdir()):
            if not folder.is_dir():
                continue
            table_name = folder.name
            jsonl_files = sorted(folder.glob('*.jsonl'))
            if not jsonl_files:
                continue

            first_sample = None
            for fn in jsonl_files:
                rows = read_jsonl_file(fn)
                if rows:
                    first_sample = rows[0]
                    break
            if not first_sample:
                continue

            create_table(conn, table_name, first_sample)

            for fn in jsonl_files:
                rows = read_jsonl_file(fn)
                if rows:
                    ingest_table(conn, table_name, rows)

        conn.commit()
        print('Ingestion completed into', DB_PATH)
    finally:
        conn.close()


if __name__ == '__main__':
    build_db()
