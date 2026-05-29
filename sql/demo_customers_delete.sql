-- Delete all demo customers and their service locations.
-- Locations are deleted first to satisfy the FK constraint.
-- On PostgreSQL (Supabase) the FK has ON DELETE CASCADE, so the
-- second statement alone is sufficient; both are included for portability.

DELETE FROM cust_customerlocation
WHERE customer_id IN (
    SELECT id FROM cust_customer WHERE demo = TRUE
);

DELETE FROM cust_customer WHERE demo = TRUE;
