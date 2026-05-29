-- Delete all jobs tied to demo customers.
-- TestResult.job_id is SET NULL automatically via FK constraint.

DELETE FROM technician_job
WHERE customer_ref_id IN (
    SELECT id FROM cust_customer WHERE demo = TRUE
);
