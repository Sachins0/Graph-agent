import sqlite3
from pathlib import Path
from typing import Dict, List, Any, Tuple
import networkx as nx

DB_PATH = Path(__file__).resolve().parent / 'o2c.db'


class O2CGraphBuilder:
    def __init__(self):
        self.graph = nx.DiGraph()
        self.conn = sqlite3.connect(DB_PATH)
        self.conn.row_factory = sqlite3.Row

    def build(self):
        """Build the complete O2C graph from database."""
        self._add_sales_order_nodes_edges()
        self._add_delivery_nodes_edges()
        self._add_billing_nodes_edges()
        self._add_payment_nodes_edges()
        self._add_customer_nodes()
        self._add_product_nodes()
        return self.graph

    def _add_sales_order_nodes_edges(self):
        """Create sales order nodes and link to items."""
        cursor = self.conn.cursor()
        
        # Sales order headers
        cursor.execute("SELECT salesOrder, soldToParty, totalNetAmount, creationDate FROM sales_order_headers LIMIT 500")
        for row in cursor.fetchall():
            so_id = f"SO:{row['salesOrder']}"
            self.graph.add_node(
                so_id,
                type='SalesOrderHeader',
                salesOrder=row['salesOrder'],
                customer=row['soldToParty'],
                netAmount=row['totalNetAmount'],
                creationDate=row['creationDate'],
                label=f"SO {row['salesOrder']}"
            )
        
        # Sales order items and link to sales orders
        cursor.execute("SELECT salesOrder, salesOrderItem, material, requestedQuantity FROM sales_order_items LIMIT 1000")
        for row in cursor.fetchall():
            so_id = f"SO:{row['salesOrder']}"
            soi_id = f"SOI:{row['salesOrder']}:{row['salesOrderItem']}"
            
            self.graph.add_node(
                soi_id,
                type='SalesOrderItem',
                salesOrder=row['salesOrder'],
                item=row['salesOrderItem'],
                material=row['material'],
                quantity=row['requestedQuantity'],
                label=f"Item {row['salesOrderItem']}"
            )
            
            self.graph.add_edge(so_id, soi_id, relationship='contains_item')

    def _add_delivery_nodes_edges(self):
        """Create delivery nodes and link to sales orders & items."""
        cursor = self.conn.cursor()
        
        # Delivery headers
        cursor.execute("SELECT deliveryDocument, shippingPoint FROM outbound_delivery_headers LIMIT 500")
        for row in cursor.fetchall():
            dh_id = f"DH:{row['deliveryDocument']}"
            self.graph.add_node(
                dh_id,
                type='DeliveryHeader',
                deliveryDocument=row['deliveryDocument'],
                shippingPoint=row['shippingPoint'],
                label=f"Delivery {row['deliveryDocument']}"
            )
        
        # Delivery items and link to sales orders/items
        cursor.execute("""
            SELECT deliveryDocument, deliveryDocumentItem, referenceSdDocument, referenceSdDocumentItem, plant
            FROM outbound_delivery_items LIMIT 1000
        """)
        for row in cursor.fetchall():
            dh_id = f"DH:{row['deliveryDocument']}"
            di_id = f"DI:{row['deliveryDocument']}:{row['deliveryDocumentItem']}"
            
            self.graph.add_node(
                di_id,
                type='DeliveryItem',
                deliveryDocument=row['deliveryDocument'],
                item=row['deliveryDocumentItem'],
                plant=row['plant'],
                label=f"DI {row['deliveryDocumentItem']}"
            )
            
            # Link delivery item to delivery header
            self.graph.add_edge(dh_id, di_id, relationship='contains_item')
            
            # Link to sales order item if reference exists
            if row['referenceSdDocument']:
                soi_id = f"SOI:{row['referenceSdDocument']}:{row['referenceSdDocumentItem']}"
                if self.graph.has_node(soi_id):
                    self.graph.add_edge(soi_id, di_id, relationship='fulfilled_by')

    def _add_billing_nodes_edges(self):
        """Create billing document nodes and link to deliveries."""
        cursor = self.conn.cursor()
        
        # Billing document headers
        cursor.execute("SELECT billingDocument, soldToParty, totalNetAmount FROM billing_document_headers LIMIT 500")
        for row in cursor.fetchall():
            bh_id = f"BH:{row['billingDocument']}"
            self.graph.add_node(
                bh_id,
                type='BillingHeader',
                billingDocument=row['billingDocument'],
                customer=row['soldToParty'],
                netAmount=row['totalNetAmount'],
                label=f"Invoice {row['billingDocument']}"
            )
        
        # Billing document items and link to delivery items
        cursor.execute("""
            SELECT billingDocument, billingDocumentItem, material, referenceSdDocument, referenceSdDocumentItem
            FROM billing_document_items LIMIT 1000
        """)
        for row in cursor.fetchall():
            bh_id = f"BH:{row['billingDocument']}"
            bi_id = f"BI:{row['billingDocument']}:{row['billingDocumentItem']}"
            
            self.graph.add_node(
                bi_id,
                type='BillingItem',
                billingDocument=row['billingDocument'],
                item=row['billingDocumentItem'],
                material=row['material'],
                label=f"BI {row['billingDocumentItem']}"
            )
            
            # Link billing item to billing header
            self.graph.add_edge(bh_id, bi_id, relationship='contains_item')
            
            # Link to delivery item if reference exists
            if row['referenceSdDocument']:
                di_id = f"DI:{row['referenceSdDocument']}:{row['referenceSdDocumentItem']}"
                if self.graph.has_node(di_id):
                    self.graph.add_edge(di_id, bi_id, relationship='billed_from')

    def _add_payment_nodes_edges(self):
        """Create payment/journal entry nodes."""
        cursor = self.conn.cursor()
        
        # Journal entries (accounts receivable)
        cursor.execute("""
            SELECT accountingDocument, referenceDocument, customer, amountInTransactionCurrency
            FROM journal_entry_items_accounts_receivable LIMIT 500
        """)
        for row in cursor.fetchall():
            je_id = f"JE:{row['accountingDocument']}"
            
            self.graph.add_node(
                je_id,
                type='JournalEntry',
                accountingDocument=row['accountingDocument'],
                referenceDocument=row['referenceDocument'],
                customer=row['customer'],
                amount=row['amountInTransactionCurrency'],
                label=f"Journal {row['accountingDocument']}"
            )
            
            # Link to billing if reference exists
            if row['referenceDocument']:
                bh_id = f"BH:{row['referenceDocument']}"
                if self.graph.has_node(bh_id):
                    self.graph.add_edge(bh_id, je_id, relationship='recorded_in_je')
        
        # Payments (accounts receivable)
        cursor.execute("""
            SELECT accountingDocument, customer, amountInTransactionCurrency
            FROM payments_accounts_receivable LIMIT 500
        """)
        seen = set()
        for row in cursor.fetchall():
            pay_id = f"PAY:{row['accountingDocument']}"
            if pay_id not in seen:
                seen.add(pay_id)
                self.graph.add_node(
                    pay_id,
                    type='Payment',
                    accountingDocument=row['accountingDocument'],
                    customer=row['customer'],
                    amount=row['amountInTransactionCurrency'],
                    label=f"Payment {row['accountingDocument']}"
                )

    def _add_customer_nodes(self):
        """Add customer/business partner nodes."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT businessPartner FROM business_partners LIMIT 500")
        for row in cursor.fetchall():
            cust_id = f"CUST:{row['businessPartner']}"
            self.graph.add_node(
                cust_id,
                type='Customer',
                businessPartner=row['businessPartner'],
                label=f"Customer {row['businessPartner']}"
            )
            
            # Link all sales orders to this customer
            for node in list(self.graph.nodes()):
                if node.startswith('SO:'):
                    node_data = self.graph.nodes[node]
                    if node_data.get('customer') == row['businessPartner']:
                        self.graph.add_edge(cust_id, node, relationship='places_order')

    def _add_product_nodes(self):
        """Add product nodes."""
        cursor = self.conn.cursor()
        
        # Get products from products table
        cursor.execute("SELECT product FROM products LIMIT 500")
        prod_ids = set()
        for row in cursor.fetchall():
            prod_id = f"PROD:{row[0]}"
            prod_ids.add(prod_id)
            if prod_id not in self.graph:
                self.graph.add_node(prod_id, type='Product', product=row[0], label=row[0])
        
        # Also add materials from sales order items that aren't in products table
        for node in list(self.graph.nodes()):
            if node.startswith('SOI:'):
                material = self.graph.nodes[node].get('material')
                if material:
                    prod_id = f"PROD:{material}"
                    if prod_id not in self.graph and prod_id not in prod_ids:
                        self.graph.add_node(prod_id, type='Product', material=material, label=material)
                    if self.graph.has_node(prod_id):
                        self.graph.add_edge(node, prod_id, relationship='includes_product')

    def to_json(self) -> Dict[str, Any]:
        """Serialize graph to JSON format for API."""
        nodes = []
        edges = []
        
        for node_id, node_data in self.graph.nodes(data=True):
            nodes.append({
                'id': node_id,
                'label': node_data.get('label', node_id),
                'type': node_data.get('type', 'Unknown'),
                'properties': {k: v for k, v in node_data.items() if k not in ['label', 'type']}
            })
        
        for source, target, edge_data in self.graph.edges(data=True):
            edges.append({
                'source': source,
                'target': target,
                'relationship': edge_data.get('relationship', 'related_to')
            })
        
        return {'nodes': nodes, 'edges': edges}

    def close(self):
        self.conn.close()


def build_graph() -> nx.DiGraph:
    builder = O2CGraphBuilder()
    graph = builder.build()
    builder.close()
    return graph


def get_graph_json() -> Dict[str, Any]:
    builder = O2CGraphBuilder()
    graph = builder.build()
    result = builder.to_json()
    builder.close()
    return result
