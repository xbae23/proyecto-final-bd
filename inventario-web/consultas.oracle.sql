-- Ejecutar en el Worksheet de Oracle FreeSQL después de iniciar la app.

-- Productos con su categoría y proveedor (JOIN).
SELECT p.sku, p.name, c.name AS categoria, s.name AS proveedor, p.stock, p.price
FROM inv_products p
JOIN inv_categories c ON c.id = p.category_id
JOIN inv_suppliers s ON s.id = p.supplier_id
ORDER BY p.name;

-- Existencias bajas.
SELECT sku, name, stock, min_stock
FROM inv_products
WHERE stock <= min_stock
ORDER BY stock;

-- Ingresos y utilidad por producto (GROUP BY).
SELECT p.sku, p.name, SUM(i.quantity) AS unidades,
       SUM(i.quantity * i.unit_price) AS ingresos,
       SUM(i.quantity * (i.unit_price - i.unit_cost)) AS ganancia_bruta
FROM inv_sale_items i
JOIN inv_products p ON p.id = i.product_id
GROUP BY p.sku, p.name
ORDER BY ingresos DESC;

-- Facturas, clientes e importes.
SELECT v.invoice, v.created_at, c.name AS cliente, v.total, v.gain
FROM inv_sales v
JOIN inv_customers c ON c.id = v.customer_id
ORDER BY v.created_at DESC;

-- Balance de movimientos por producto.
SELECT p.name, SUM(CASE WHEN m.quantity > 0 THEN m.quantity ELSE 0 END) AS entradas,
       SUM(CASE WHEN m.quantity < 0 THEN -m.quantity ELSE 0 END) AS salidas,
       SUM(m.quantity) AS saldo
FROM inv_movements m
JOIN inv_products p ON p.id = m.product_id
GROUP BY p.name
ORDER BY p.name;
