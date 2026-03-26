import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional
import networkx as nx

DB_PATH = Path(__file__).resolve().parent / 'o2c.db'

# Module-level cache
_graph_cache: Optional[Dict[str, Any]] = None
_nx_graph_cache: Optional[nx.DiGraph] = None


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

    # ── Sales Orders ─────────────────────────────────────────────

    def _add_sales_orders(self):
        cur = self.conn.cursor()

        cur.execute("""
            SELECT salesOrder, soldToParty, totalNetAmount, creationDate,
                   overallDeliveryStatus, overallBillingStatus
            FROM sales_order_headers
        """)
        for row in cur.fetchall():
            so_id = f"SO:{row['salesOrder']}"
            self.graph.add_node(so_id,
                type='SalesOrderHeader',
                label=f"SO {row['salesOrder']}",
                salesOrder=row['salesOrder'],
                customer=row['soldToParty'],
                netAmount=row['totalNetAmount'],
                creationDate=row['creationDate'],
                deliveryStatus=row['overallDeliveryStatus'],
                billingStatus=row['overallBillingStatus'],
            )

        cur.execute("""
            SELECT salesOrder, salesOrderItem, material, requestedQuantity, netAmount, plant
            FROM sales_order_items
        """)
        for row in cur.fetchall():
            so_id  = f"SO:{row['salesOrder']}"
            soi_id = f"SOI:{row['salesOrder']}:{row['salesOrderItem']}"
            self.graph.add_node(soi_id,
                type='SalesOrderItem',
                label=f"Item {row['salesOrderItem']}",
                salesOrder=row['salesOrder'],
                item=row['salesOrderItem'],
                material=row['material'],
                quantity=row['requestedQuantity'],
                netAmount=row['netAmount'],
                plant=row['plant'],
            )
            if self.graph.has_node(so_id):
                self.graph.add_edge(so_id, soi_id, relationship='contains_item')

    # ── Deliveries ───────────────────────────────────────────────

    def _add_deliveries(self):
        cur = self.conn.cursor()

        cur.execute("""
            SELECT deliveryDocument, shippingPoint, creationDate,
                   soldToParty, overallGoodsMovementStatus
            FROM outbound_delivery_headers
        """)
        for row in cur.fetchall():
            dh_id = f"DH:{row['deliveryDocument']}"
            self.graph.add_node(dh_id,
                type='DeliveryHeader',
                label=f"Delivery {row['deliveryDocument']}",
                deliveryDocument=row['deliveryDocument'],
                shippingPoint=row['shippingPoint'],
                creationDate=row['creationDate'],
                customer=row['soldToParty'],
                goodsMovementStatus=row['overallGoodsMovementStatus'],
            )

        cur.execute("""
            SELECT deliveryDocument, deliveryDocumentItem,
                   referenceSdDocument, referenceSdDocumentItem,
                   material, actualDeliveryQuantity, plant
            FROM outbound_delivery_items
        """)
        for row in cur.fetchall():
            dh_id = f"DH:{row['deliveryDocument']}"
            di_id = f"DI:{row['deliveryDocument']}:{row['deliveryDocumentItem']}"
            self.graph.add_node(di_id,
                type='DeliveryItem',
                label=f"DI {row['deliveryDocumentItem']}",
                deliveryDocument=row['deliveryDocument'],
                item=row['deliveryDocumentItem'],
                material=row['material'],
                quantity=row['actualDeliveryQuantity'],
                plant=row['plant'],
            )
            if self.graph.has_node(dh_id):
                self.graph.add_edge(dh_id, di_id, relationship='contains_item')

            if row['referenceSdDocument']:
                soi_id = f"SOI:{row['referenceSdDocument']}:{row['referenceSdDocumentItem']}"
                if self.graph.has_node(soi_id):
                    self.graph.add_edge(soi_id, di_id, relationship='fulfilled_by')

    # ── Billing ──────────────────────────────────────────────────

    def _add_billings(self):
        cur = self.conn.cursor()

        cur.execute("""
            SELECT billingDocument, soldToParty, totalNetAmount,
                   billingDocumentDate, billingDocumentIsCancelled,
                   accountingDocument, fiscalYear
            FROM billing_document_headers
        """)
        for row in cur.fetchall():
            bh_id = f"BH:{row['billingDocument']}"
            self.graph.add_node(bh_id,
                type='BillingHeader',
                label=f"Invoice {row['billingDocument']}",
                billingDocument=row['billingDocument'],
                customer=row['soldToParty'],
                netAmount=row['totalNetAmount'],
                billingDate=row['billingDocumentDate'],
                isCancelled=bool(row['billingDocumentIsCancelled']),
                accountingDocument=row['accountingDocument'],
            )

        cur.execute("""
            SELECT billingDocument, billingDocumentItem, material,
                   netAmount, referenceSdDocument, referenceSdDocumentItem
            FROM billing_document_items
        """)
        for row in cur.fetchall():
            bh_id = f"BH:{row['billingDocument']}"
            bi_id = f"BI:{row['billingDocument']}:{row['billingDocumentItem']}"
            self.graph.add_node(bi_id,
                type='BillingItem',
                label=f"BI {row['billingDocumentItem']}",
                billingDocument=row['billingDocument'],
                item=row['billingDocumentItem'],
                material=row['material'],
                netAmount=row['netAmount'],
            )
            if self.graph.has_node(bh_id):
                self.graph.add_edge(bh_id, bi_id, relationship='contains_item')

            # BillingItem → DeliveryItem
            if row['referenceSdDocument'] and row['referenceSdDocumentItem']:
                di_id = f"DI:{row['referenceSdDocument']}:{row['referenceSdDocumentItem']}"
                if self.graph.has_node(di_id):
                    self.graph.add_edge(di_id, bi_id, relationship='billed_from')

    # ── Payments & Journal Entries ───────────────────────────────

    def _add_payments(self):
        cur = self.conn.cursor()

        cur.execute("""
            SELECT accountingDocument, referenceDocument, customer,
                   amountInTransactionCurrency, postingDate
            FROM journal_entry_items_accounts_receivable
        """)
        seen_je = set()
        for row in cur.fetchall():
            je_id = f"JE:{row['accountingDocument']}"
            if je_id not in seen_je:
                seen_je.add(je_id)
                self.graph.add_node(je_id,
                    type='JournalEntry',
                    label=f"Journal {row['accountingDocument']}",
                    accountingDocument=row['accountingDocument'],
                    referenceDocument=row['referenceDocument'],
                    customer=row['customer'],
                    amount=row['amountInTransactionCurrency'],
                    postingDate=row['postingDate'],
                )
            # BillingHeader → JournalEntry
            if row['referenceDocument']:
                bh_id = f"BH:{row['referenceDocument']}"
                if self.graph.has_node(bh_id):
                    self.graph.add_edge(bh_id, je_id, relationship='recorded_in_je')

        cur.execute("""
            SELECT accountingDocument, customer,
                   amountInTransactionCurrency, clearingAccountingDocument, clearingDate
            FROM payments_accounts_receivable
        """)
        seen_pay = set()
        for row in cur.fetchall():
            pay_id = f"PAY:{row['accountingDocument']}"
            if pay_id not in seen_pay:
                seen_pay.add(pay_id)
                self.graph.add_node(pay_id,
                    type='Payment',
                    label=f"Payment {row['accountingDocument']}",
                    accountingDocument=row['accountingDocument'],
                    customer=row['customer'],
                    amount=row['amountInTransactionCurrency'],
                    clearingDocument=row['clearingAccountingDocument'],
                    clearingDate=row['clearingDate'],
                    isCleared=bool(row['clearingAccountingDocument']),
                )
                # Payment → JournalEntry (same accounting doc)
                je_id = f"JE:{row['accountingDocument']}"
                if self.graph.has_node(je_id):
                    self.graph.add_edge(je_id, pay_id, relationship='settled_by')

    # ── Customers ────────────────────────────────────────────────

    def _add_customers(self):
        cur = self.conn.cursor()

        cur.execute("""
            SELECT businessPartner, businessPartnerName, country, cityName
            FROM business_partners
        """)
        for row in cur.fetchall():
            cust_id = f"CUST:{row['businessPartner']}"
            self.graph.add_node(cust_id,
                type='Customer',
                label=row['businessPartnerName'] or f"Customer {row['businessPartner']}",
                businessPartner=row['businessPartner'],
                name=row['businessPartnerName'],
                country=row['country'],
                city=row['cityName'],
            )

        # Build a lookup: customer_id → list of SO node IDs (O(1) per customer)
        customer_to_so: Dict[str, List[str]] = {}
        for node_id, data in self.graph.nodes(data=True):
            if data.get('type') == 'SalesOrderHeader':
                cid = data.get('customer')
                if cid:
                    customer_to_so.setdefault(cid, []).append(node_id)
            elif data.get('type') == 'BillingHeader':
                cid = data.get('customer')
                if cid:
                    cust_id = f"CUST:{cid}"
                    if self.graph.has_node(cust_id):
                        self.graph.add_edge(cust_id, node_id, relationship='billed_to')

        for node_id, data in self.graph.nodes(data=True):
            if data.get('type') == 'Customer':
                bp = data.get('businessPartner')
                for so_id in customer_to_so.get(bp, []):
                    self.graph.add_edge(node_id, so_id, relationship='places_order')

    # ── Products ─────────────────────────────────────────────────

    def _add_products(self):
        cur = self.conn.cursor()

        # products table uses 'material' as PK (from ingest schema)
        try:
            cur.execute("SELECT material FROM products")
            for row in cur.fetchall():
                mat = row[0]
                if mat:
                    prod_id = f"PROD:{mat}"
                    if prod_id not in self.graph:
                        self.graph.add_node(prod_id,
                            type='Product',
                            label=mat,
                            material=mat,
                        )
        except Exception:
            pass  # products table might have different schema

        # Try to enrich product names from product_descriptions
        try:
            cur.execute("""
                SELECT material, materialDescription
                FROM product_descriptions
                WHERE language = 'EN'
            """)
            for row in cur.fetchall():
                prod_id = f"PROD:{row[0]}"
                if self.graph.has_node(prod_id):
                    self.graph.nodes[prod_id]['label'] = row[1] or row[0]
        except Exception:
            pass

        # Link SalesOrderItems → Products
        for node_id, data in self.graph.nodes(data=True):
            if data.get('type') == 'SalesOrderItem':
                material = data.get('material')
                if material:
                    prod_id = f"PROD:{material}"
                    if prod_id not in self.graph:
                        self.graph.add_node(prod_id,
                            type='Product', label=material, material=material
                        )
                    self.graph.add_edge(node_id, prod_id, relationship='includes_product')

    # ── Serialization ─────────────────────────────────────────────

    def to_json(self) -> Dict[str, Any]:
        nodes = []
        for node_id, data in self.graph.nodes(data=True):
            nodes.append({
                'id':         node_id,
                'label':      data.get('label', node_id),
                'type':       data.get('type', 'Unknown'),
                'properties': {k: v for k, v in data.items() if k not in ('label', 'type')},
            })

        edges = []
        for src, tgt, data in self.graph.edges(data=True):
            edges.append({
                'source':       src,
                'target':       tgt,
                'relationship': data.get('relationship', 'related_to'),
            })

        return {'nodes': nodes, 'edges': edges}

    def get_stats(self) -> Dict[str, Any]:
        node_types: Dict[str, int] = {}
        edge_types: Dict[str, int] = {}
        for _, data in self.graph.nodes(data=True):
            t = data.get('type', 'Unknown')
            node_types[t] = node_types.get(t, 0) + 1
        for _, _, data in self.graph.edges(data=True):
            r = data.get('relationship', 'related_to')
            edge_types[r] = edge_types.get(r, 0) + 1
        return {
            'total_nodes':      self.graph.number_of_nodes(),
            'total_edges':      self.graph.number_of_edges(),
            'node_type_counts': node_types,
            'edge_type_counts': edge_types,
        }

    def trace_flow(self, billing_document_id: str) -> Dict[str, Any]:
        """Trace full O2C flow: SO → Delivery → Billing → Journal → Payment."""
        bh_id = f"BH:{billing_document_id}"
        if not self.graph.has_node(bh_id):
            return {'error': f'Billing document {billing_document_id} not found'}

        flow_nodes: set = {bh_id}

        # BillingHeader → BillingItems
        for _, bi_id in self.graph.out_edges(bh_id):
            if self.graph.nodes[bi_id].get('type') == 'BillingItem':
                flow_nodes.add(bi_id)
                # BillingItem ← DeliveryItem
                for di_id, _ in self.graph.in_edges(bi_id):
                    if self.graph.nodes[di_id].get('type') == 'DeliveryItem':
                        flow_nodes.add(di_id)
                        # DeliveryItem → DeliveryHeader
                        for dh_id, _ in self.graph.in_edges(di_id):
                            if self.graph.nodes[dh_id].get('type') == 'DeliveryHeader':
                                flow_nodes.add(dh_id)
                        # DeliveryItem ← SalesOrderItem
                        for soi_id, _ in self.graph.in_edges(di_id):
                            if self.graph.nodes[soi_id].get('type') == 'SalesOrderItem':
                                flow_nodes.add(soi_id)
                                for so_id, _ in self.graph.in_edges(soi_id):
                                    if self.graph.nodes[so_id].get('type') == 'SalesOrderHeader':
                                        flow_nodes.add(so_id)

        # BillingHeader → JournalEntry → Payment
        for _, je_id in self.graph.out_edges(bh_id):
            if self.graph.nodes[je_id].get('type') == 'JournalEntry':
                flow_nodes.add(je_id)
                for _, pay_id in self.graph.out_edges(je_id):
                    if self.graph.nodes[pay_id].get('type') == 'Payment':
                        flow_nodes.add(pay_id)

        subgraph = self.graph.subgraph(flow_nodes)
        builder  = O2CGraphBuilder.__new__(O2CGraphBuilder)
        builder.graph = subgraph
        return builder.to_json()

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
    """Trace full O2C flow using cached graph."""
    get_graph_json()  # ensure cache is warm
    builder = O2CGraphBuilder.__new__(O2CGraphBuilder)
    builder.graph = _nx_graph_cache
    return builder.trace_flow(billing_document_id)
