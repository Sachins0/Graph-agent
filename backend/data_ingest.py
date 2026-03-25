import json
import os
from pathlib import Path
from sqlalchemy import create_engine, Column, String, DateTime, Boolean, Integer, Float, MetaData, Table

DATA_DIR = Path(__file__).resolve().parent.parent / 'sap-o2c-data'
DB_PATH = Path(__file__).resolve().parent / 'o2c_graph.db'

# simplified data model used for ingestion

def create_db():
    engine = create_engine(f"sqlite:///{DB_PATH}", echo=False, future=True)
    metadata = MetaData()

    # example table
    sales_order_headers = Table(
        'sales_order_headers', metadata,
        Column('salesOrder', String, primary_key=True),
        Column('soldToParty', String),
        Column('creationDate', String),
        Column('totalNetAmount', String),
    )

    metadata.create_all(engine)
    return engine


def read_jsonl(path):
    with open(path, 'r', encoding='utf8') as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def load_sales_order_headers(engine):
    table = engine.table_names()  # placeholder, SQLAlchemy 2.0 use inspect
    # actual implementation later
    pass

if __name__ == '__main__':
    print('Data ingestion skeleton')
