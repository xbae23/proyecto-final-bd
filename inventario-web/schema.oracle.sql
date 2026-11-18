CREATE TABLE inv_categories (id VARCHAR2(12) PRIMARY KEY, name VARCHAR2(120) NOT NULL UNIQUE);
CREATE TABLE inv_suppliers (id VARCHAR2(12) PRIMARY KEY, name VARCHAR2(160) NOT NULL, email VARCHAR2(180), phone VARCHAR2(40));
CREATE TABLE inv_customers (id VARCHAR2(12) PRIMARY KEY, name VARCHAR2(160) NOT NULL, email VARCHAR2(180), phone VARCHAR2(40));
CREATE TABLE inv_products (id VARCHAR2(12) PRIMARY KEY, sku VARCHAR2(40) NOT NULL UNIQUE, name VARCHAR2(180) NOT NULL, category_id VARCHAR2(12) REFERENCES inv_categories(id), supplier_id VARCHAR2(12) REFERENCES inv_suppliers(id), cost NUMBER(12,2) NOT NULL CHECK (cost>=0), price NUMBER(12,2) NOT NULL CHECK (price>0), stock NUMBER(10) DEFAULT 0 NOT NULL CHECK (stock>=0), min_stock NUMBER(10) DEFAULT 10 NOT NULL, active NUMBER(1) DEFAULT 1 NOT NULL, created_at VARCHAR2(40) NOT NULL);
CREATE TABLE inv_movements (id VARCHAR2(12) PRIMARY KEY, product_id VARCHAR2(12) NOT NULL REFERENCES inv_products(id), kind VARCHAR2(20) NOT NULL, quantity NUMBER(10) NOT NULL, note VARCHAR2(500), created_at VARCHAR2(40) NOT NULL);
CREATE TABLE inv_sales (id VARCHAR2(12) PRIMARY KEY, invoice VARCHAR2(30) NOT NULL UNIQUE, customer_id VARCHAR2(12) NOT NULL REFERENCES inv_customers(id), total NUMBER(12,2) NOT NULL, gain NUMBER(12,2) NOT NULL, created_at VARCHAR2(40) NOT NULL);
CREATE TABLE inv_sale_items (id VARCHAR2(12) PRIMARY KEY, sale_id VARCHAR2(12) NOT NULL REFERENCES inv_sales(id), product_id VARCHAR2(12) NOT NULL REFERENCES inv_products(id), quantity NUMBER(10) NOT NULL CHECK (quantity>0), unit_price NUMBER(12,2) NOT NULL, unit_cost NUMBER(12,2) NOT NULL);
CREATE INDEX idx_inv_movements_product ON inv_movements(product_id);
CREATE INDEX idx_inv_items_sale ON inv_sale_items(sale_id);
