import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import networkx as nx

DB_PATH = Path(__file__).resolve().parent / 'o2c.db'

_graph_cache:    Optional[Dict[str, Any]] = None
_nx_graph_cache: Optional[nx.DiGraph]    = None


def _get_columns(conn: sqlite3.Connection, table: str) -> Set[str]:
    """Return the set of column names that actually exist in a table."""
    try:
        cur = conn.execute(f"PRAGMA table_info('{table}')")
        return {row[1] for row in cur.fetchall()}
    except Exception:
        return set()


def _safe_select(conn: sqlite3.Connection, table: str, wanted: List[str]) -> List[sqlite3.Row]:
    """SELECT only the columns from `wanted` that actually exist in the table."""
    existing = _get_columns(conn, table)
    cols = [c for c in wanted if c in existing]
    if not cols:
        return []
    cur = conn.execute(f"SELECT {', '.join(cols)} FROM \"{table}\"")
    cur.row_factory = None
    # Return list of dicts
    col_names = [c for c in cols]
    return [dict(zip(col_names, row)) for row in cur.fetchall()]


class O2CGraphBuilder:
    def __init__(self):
        self.graph = nx.DiGraph()
        self.conn  = sqlite3.connect(DB_PATH)
        self.conn.row_factory = sqlite3.Row

    def build(self) -> nx.DiGraph:
        self._add_sales_orders()
        self._add_deliveries()
        self._add_billings()
        self._add_payments()
        self._add_customers()
        self._add_products()
        return self.graph

    # ── helpers ──────────────────────────────────────────────────

    def _cols(self, table: str) -> Set[str]:
        return _get_columns(self.conn, table)

    def _pick(self, row, key: str, default=None):
        """Safely get a value from a sqlite3.Row or dict."""
        try:
            return row[key]
        except (KeyError, IndexError):
            return default

    # ── Sales Orders ─────────────────────────────────────────────

    def _add_sales_orders(self):
        cur = self.conn.cursor()

        # Build SELECT using only available columns
        avail = self._cols('sales_order_headers')
        wanted_hdr = [
            'salesOrder', 'soldToParty', 'totalNetAmount', 'creationDate',
            'overallDeliveryStatus',
            'overallOrdReltdBillgStatus', 
            'salesOrderType', 'salesOrganization', 'transactionCurrency'
        ]

        cols_hdr = [c for c in wanted_hdr if c in avail]
        if not cols_hdr or 'salesOrder' not in avail:
            print("  ⚠ sales_order_headers: missing salesOrder column, skipping")
            return

        cur.execute(f"SELECT {', '.join(cols_hdr)} FROM sales_order_headers")
        for row in cur.fetchall():
            so_id = f"SO:{row['salesOrder']}"
            self.graph.add_node(so_id,
                type='SalesOrderHeader',
                label=f"SO {row['salesOrder']}",
                salesOrder=str(row['salesOrder']),
                customer=self._pick(row, 'soldToParty', ''),
                netAmount=self._pick(row, 'totalNetAmount') or self._pick(row, 'netAmount', 0),
                creationDate=self._pick(row, 'creationDate', ''),
                deliveryStatus=self._pick(row, 'overallDeliveryStatus', ''),
                billingStatus=self._pick(row, 'overallOrdReltdBillgStatus', ''),
            )

        avail_itm = self._cols('sales_order_items')
        wanted_itm = ['salesOrder', 'salesOrderItem', 'material',
                      'requestedQuantity', 'netAmount', 'plant']
        cols_itm = [c for c in wanted_itm if c in avail_itm]
        if cols_itm and 'salesOrder' in avail_itm:
            cur.execute(f"SELECT {', '.join(cols_itm)} FROM sales_order_items")
            for row in cur.fetchall():
                so_id  = f"SO:{row['salesOrder']}"
                soi_id = f"SOI:{row['salesOrder']}:{self._pick(row, 'salesOrderItem', '0')}"
                self.graph.add_node(soi_id,
                    type='SalesOrderItem',
                    label=f"Item {self._pick(row, 'salesOrderItem', '')}",
                    salesOrder=str(row['salesOrder']),
                    item=str(self._pick(row, 'salesOrderItem', '')),
                    material=self._pick(row, 'material', ''),
                    quantity=self._pick(row, 'requestedQuantity', 0),
                    netAmount=self._pick(row, 'netAmount', 0),
                    plant=self._pick(row, 'plant', ''),
                )
                if self.graph.has_node(so_id):
                    self.graph.add_edge(so_id, soi_id, relationship='contains_item')

    # ── Deliveries ───────────────────────────────────────────────

    def _add_deliveries(self):
        cur = self.conn.cursor()

        avail = self._cols('outbound_delivery_headers')
        wanted = [
            'deliveryDocument', 'shippingPoint', 'creationDate',
            'overallGoodsMovementStatus', 'overallPickingStatus',
            'deliveryBlockReason'
        ]
        cols = [c for c in wanted if c in avail]
        if not cols or 'deliveryDocument' not in avail:
            print("  ⚠ outbound_delivery_headers: missing deliveryDocument, skipping")
            return

        cur.execute(f"SELECT {', '.join(cols)} FROM outbound_delivery_headers")
        for row in cur.fetchall():
            dh_id = f"DH:{row['deliveryDocument']}"
            self.graph.add_node(dh_id,
                type='DeliveryHeader',
                label=f"Delivery {row['deliveryDocument']}",
                deliveryDocument=str(row['deliveryDocument']),
                shippingPoint=self._pick(row, 'shippingPoint', ''),
                creationDate=self._pick(row, 'creationDate', ''),
                customer=self._pick(row, 'soldToParty', ''),
            )

        avail_itm = self._cols('outbound_delivery_items')
        wanted_itm = ['deliveryDocument', 'deliveryDocumentItem',
                      'referenceSdDocument', 'referenceSdDocumentItem',
                      'material', 'actualDeliveryQuantity', 'plant']
        cols_itm = [c for c in wanted_itm if c in avail_itm]
        if cols_itm and 'deliveryDocument' in avail_itm:
            cur.execute(f"SELECT {', '.join(cols_itm)} FROM outbound_delivery_items")
            for row in cur.fetchall():
                dh_id = f"DH:{row['deliveryDocument']}"
                di_id = f"DI:{row['deliveryDocument']}:{self._pick(row, 'deliveryDocumentItem', '0')}"
                self.graph.add_node(di_id,
                    type='DeliveryItem',
                    label=f"DI {self._pick(row, 'deliveryDocumentItem', '')}",
                    deliveryDocument=str(row['deliveryDocument']),
                    item=str(self._pick(row, 'deliveryDocumentItem', '')),
                    material=self._pick(row, 'material', ''),
                    plant=self._pick(row, 'plant', ''),
                )
                if self.graph.has_node(dh_id):
                    self.graph.add_edge(dh_id, di_id, relationship='contains_item')
                ref_so  = self._pick(row, 'referenceSdDocument')
                ref_itm = self._pick(row, 'referenceSdDocumentItem')
                if ref_so and ref_itm:
                    soi_id = f"SOI:{ref_so}:{ref_itm}"
                    if self.graph.has_node(soi_id):
                        self.graph.add_edge(soi_id, di_id, relationship='fulfilled_by')

    # ── Billing ──────────────────────────────────────────────────

    def _add_billings(self):
        cur = self.conn.cursor()

        avail = self._cols('billing_document_headers')
        wanted = [
            'billingDocument', 'soldToParty', 'totalNetAmount',
            'billingDocumentDate', 'creationDate',
            'billingDocumentIsCancelled', 'cancelledBillingDocument',
            'accountingDocument', 'fiscalYear', 'companyCode',
            'transactionCurrency', 'billingDocumentType'
        ]
        cols = [c for c in wanted if c in avail]
        if not cols or 'billingDocument' not in avail:
            print("  ⚠ billing_document_headers: missing billingDocument, skipping")
            return

        cur.execute(f"SELECT {', '.join(cols)} FROM billing_document_headers")
        for row in cur.fetchall():
            bh_id = f"BH:{row['billingDocument']}"
            self.graph.add_node(bh_id,
                type='BillingHeader',
                label=f"Invoice {row['billingDocument']}",
                billingDocument=str(row['billingDocument']),
                customer=self._pick(row, 'soldToParty', ''),
                netAmount=self._pick(row, 'totalNetAmount') or self._pick(row, 'netAmount', 0),
                billingDate=self._pick(row, 'billingDocumentDate') or self._pick(row, 'creationDate', ''),
                isCancelled=bool(self._pick(row, 'billingDocumentIsCancelled', 0)),
                accountingDocument=self._pick(row, 'accountingDocument', ''),
            )

        avail_itm = self._cols('billing_document_items')
        wanted_itm = ['billingDocument', 'billingDocumentItem', 'material',
                      'netAmount', 'referenceSdDocument', 'referenceSdDocumentItem']
        cols_itm = [c for c in wanted_itm if c in avail_itm]
        if cols_itm and 'billingDocument' in avail_itm:
            cur.execute(f"SELECT {', '.join(cols_itm)} FROM billing_document_items")
            for row in cur.fetchall():
                bh_id = f"BH:{row['billingDocument']}"
                bi_id = f"BI:{row['billingDocument']}:{self._pick(row, 'billingDocumentItem', '0')}"
                self.graph.add_node(bi_id,
                    type='BillingItem',
                    label=f"BI {self._pick(row, 'billingDocumentItem', '')}",
                    billingDocument=str(row['billingDocument']),
                    material=self._pick(row, 'material', ''),
                    netAmount=self._pick(row, 'netAmount', 0),
                )
                if self.graph.has_node(bh_id):
                    self.graph.add_edge(bh_id, bi_id, relationship='contains_item')
                ref_so  = self._pick(row, 'referenceSdDocument')
                ref_itm = self._pick(row, 'referenceSdDocumentItem')
                if ref_so and ref_itm:
                    di_id = f"DI:{ref_so}:{ref_itm}"
                    if self.graph.has_node(di_id):
                        self.graph.add_edge(di_id, bi_id, relationship='billed_from')

    # ── Payments & Journal Entries ───────────────────────────────

    def _add_payments(self):
        cur = self.conn.cursor()

        # Journal entries
        je_table = 'journal_entry_items_accounts_receivable'
        avail_je = self._cols(je_table)
        wanted_je = [
            'accountingDocument', 'accountingDocumentItem',
            'referenceDocument',           
            'customer', 'amountInTransactionCurrency',
            'postingDate', 'documentDate',
            'glAccount', 'costCenter', 'profitCenter',
            'clearingAccountingDocument', 'clearingDate'
        ]
        cols_je = [c for c in wanted_je if c in avail_je]
        seen_je: set = set()
        if cols_je and 'accountingDocument' in avail_je:
            cur.execute(f"SELECT {', '.join(cols_je)} FROM \"{je_table}\"")
            for row in cur.fetchall():
                je_id = f"JE:{row['accountingDocument']}"
                if je_id not in seen_je:
                    seen_je.add(je_id)
                    self.graph.add_node(je_id,
                        type='JournalEntry',
                        label=f"Journal {row['accountingDocument']}",
                        accountingDocument=str(row['accountingDocument']),
                        referenceDocument=self._pick(row, 'referenceDocument', ''),
                        customer=self._pick(row, 'customer', ''),
                        amount=self._pick(row, 'amountInTransactionCurrency', 0),
                        postingDate=self._pick(row, 'postingDate', ''),
                    )
                ref = self._pick(row, 'referenceDocument')
                if ref:
                    bh_id = f"BH:{ref}"
                    if self.graph.has_node(bh_id):
                        self.graph.add_edge(bh_id, je_id, relationship='recorded_in_je')

        # Payments
        pay_table = 'payments_accounts_receivable'
        avail_pay = self._cols(pay_table)
        wanted_pay = [
            'accountingDocument', 'accountingDocumentItem',
            'customer', 'amountInTransactionCurrency',
            'clearingAccountingDocument', 'clearingDate',
            'postingDate', 'invoiceReference',  
            'salesDocument', 'salesDocumentItem'
        ]
        cols_pay = [c for c in wanted_pay if c in avail_pay]
        seen_pay: set = set()
        if cols_pay and 'accountingDocument' in avail_pay:
            cur.execute(f"SELECT {', '.join(cols_pay)} FROM \"{pay_table}\"")
            for row in cur.fetchall():
                pay_id = f"PAY:{row['accountingDocument']}"
                if pay_id not in seen_pay:
                    seen_pay.add(pay_id)
                    clearing = self._pick(row, 'clearingAccountingDocument')
                    self.graph.add_node(pay_id,
                        type='Payment',
                        label=f"Payment {row['accountingDocument']}",
                        accountingDocument=str(row['accountingDocument']),
                        customer=self._pick(row, 'customer', ''),
                        amount=self._pick(row, 'amountInTransactionCurrency', 0),
                        clearingDocument=clearing or '',
                        isCleared=bool(clearing),
                    )
                    je_id = f"JE:{row['accountingDocument']}"
                    if self.graph.has_node(je_id):
                        self.graph.add_edge(je_id, pay_id, relationship='settled_by')
                        
        inv_ref = self._pick(row, 'invoiceReference')
        if inv_ref:
            bh_id = f"BH:{inv_ref}"
            if self.graph.has_node(bh_id):
                self.graph.add_edge(bh_id, pay_id, relationship='paid_by')

    # ── Customers ────────────────────────────────────────────────

    def _add_customers(self):
        cur = self.conn.cursor()

        avail = self._cols('business_partners')
        wanted = ['businessPartner', 'businessPartnerName', 'country', 'cityName']
        cols = [c for c in wanted if c in avail]
        if not cols or 'businessPartner' not in avail:
            return

        cur.execute(f"SELECT {', '.join(cols)} FROM business_partners")

        # Build lookup dict first — O(n) not O(n²)
        customer_to_so: Dict[str, List[str]] = {}
        for nid, data in self.graph.nodes(data=True):
            if data.get('type') == 'SalesOrderHeader' and data.get('customer'):
                customer_to_so.setdefault(data['customer'], []).append(nid)

        for row in cur.fetchall():
            bp      = str(row['businessPartner'])
            cust_id = f"CUST:{bp}"
            self.graph.add_node(cust_id,
                type='Customer',
                label=self._pick(row, 'businessPartnerName') or f"Customer {bp}",
                businessPartner=bp,
                name=self._pick(row, 'businessPartnerName', ''),
                country=self._pick(row, 'country', ''),
                city=self._pick(row, 'cityName', ''),
            )
            for so_id in customer_to_so.get(bp, []):
                self.graph.add_edge(cust_id, so_id, relationship='places_order')

    # ── Products ─────────────────────────────────────────────────

    def _add_products(self):
        cur = self.conn.cursor()

        avail = self._cols('products')
        # column might be 'material' or 'product'
        mat_col = 'material' if 'material' in avail else ('product' if 'product' in avail else None)

        if mat_col:
            cur.execute(f'SELECT "{mat_col}" FROM products')
            for row in cur.fetchall():
                mat = row[0]
                if mat:
                    prod_id = f"PROD:{mat}"
                    if prod_id not in self.graph:
                        self.graph.add_node(prod_id,
                            type='Product', label=str(mat), material=str(mat))

        # Enrich with descriptions
        avail_desc = self._cols('product_descriptions')
        if 'material' in avail_desc and 'materialDescription' in avail_desc:
            lang_filter = "WHERE language = 'EN'" if 'language' in avail_desc else ""
            try:
                cur.execute(f"SELECT material, materialDescription FROM product_descriptions {lang_filter}")
                for row in cur.fetchall():
                    prod_id = f"PROD:{row[0]}"
                    if self.graph.has_node(prod_id) and row[1]:
                        self.graph.nodes[prod_id]['label'] = row[1]
            except Exception:
                pass

        # Link SOI → Product
        for nid, data in list(self.graph.nodes(data=True)):
            if data.get('type') == 'SalesOrderItem':
                mat = data.get('material')
                if mat:
                    prod_id = f"PROD:{mat}"
                    if prod_id not in self.graph:
                        self.graph.add_node(prod_id,
                            type='Product', label=str(mat), material=str(mat))
                    self.graph.add_edge(nid, prod_id, relationship='includes_product')

    # ── Serialization ─────────────────────────────────────────────

    def to_json(self) -> Dict[str, Any]:
        nodes = [
            {
                'id':         nid,
                'label':      data.get('label', nid),
                'type':       data.get('type', 'Unknown'),
                'properties': {k: v for k, v in data.items() if k not in ('label', 'type')},
            }
            for nid, data in self.graph.nodes(data=True)
        ]
        edges = [
            {'source': s, 'target': t, 'relationship': d.get('relationship', 'related_to')}
            for s, t, d in self.graph.edges(data=True)
        ]
        return {'nodes': nodes, 'edges': edges}

    def trace_flow(self, billing_document_id: str) -> Dict[str, Any]:
        bh_id = f"BH:{billing_document_id}"
        if not self.graph.has_node(bh_id):
            return {'error': f'Billing document {billing_document_id} not found in graph'}

        flow_nodes: set = {bh_id}
        for _, bi_id in self.graph.out_edges(bh_id):
            if self.graph.nodes[bi_id].get('type') == 'BillingItem':
                flow_nodes.add(bi_id)
                for di_id, _ in self.graph.in_edges(bi_id):
                    if self.graph.nodes[di_id].get('type') == 'DeliveryItem':
                        flow_nodes.add(di_id)
                        for dh_id, _ in self.graph.in_edges(di_id):
                            if self.graph.nodes[dh_id].get('type') == 'DeliveryHeader':
                                flow_nodes.add(dh_id)
                        for soi_id, _ in self.graph.in_edges(di_id):
                            if self.graph.nodes[soi_id].get('type') == 'SalesOrderItem':
                                flow_nodes.add(soi_id)
                                for so_id, _ in self.graph.in_edges(soi_id):
                                    if self.graph.nodes[so_id].get('type') == 'SalesOrderHeader':
                                        flow_nodes.add(so_id)
        for _, je_id in self.graph.out_edges(bh_id):
            if self.graph.nodes[je_id].get('type') == 'JournalEntry':
                flow_nodes.add(je_id)
                for _, pay_id in self.graph.out_edges(je_id):
                    if self.graph.nodes[pay_id].get('type') == 'Payment':
                        flow_nodes.add(pay_id)

        sub = self.graph.subgraph(flow_nodes)
        tmp = O2CGraphBuilder.__new__(O2CGraphBuilder)
        tmp.graph = sub
        return tmp.to_json()

    def close(self):
        self.conn.close()


# ── Public API ────────────────────────────────────────────────────

def _build_fresh() -> tuple:
    builder = O2CGraphBuilder()
    builder.build()
    json_data = builder.to_json()
    nx_graph  = builder.graph.copy()
    builder.close()
    return json_data, nx_graph


def get_graph_json(force_rebuild: bool = False) -> Dict[str, Any]:
    global _graph_cache, _nx_graph_cache
    if _graph_cache is None or force_rebuild:
        print("Building O2C graph...")
        _graph_cache, _nx_graph_cache = _build_fresh()
        print(f"Graph ready: {len(_graph_cache['nodes'])} nodes, {len(_graph_cache['edges'])} edges")
    return _graph_cache


def get_graph_stats() -> Dict[str, Any]:
    data = get_graph_json()
    node_types: Dict[str, int] = {}
    edge_types: Dict[str, int] = {}
    for n in data['nodes']:
        t = n.get('type', 'Unknown')
        node_types[t] = node_types.get(t, 0) + 1
    for e in data['edges']:
        r = e.get('relationship', 'related_to')
        edge_types[r] = edge_types.get(r, 0) + 1
    return {
        'total_nodes':      len(data['nodes']),
        'total_edges':      len(data['edges']),
        'node_type_counts': node_types,
        'edge_type_counts': edge_types,
    }


def trace_billing_flow(billing_document_id: str) -> Dict[str, Any]:
    get_graph_json()
    builder = O2CGraphBuilder.__new__(O2CGraphBuilder)
    builder.graph = _nx_graph_cache
    return builder.trace_flow(billing_document_id)
