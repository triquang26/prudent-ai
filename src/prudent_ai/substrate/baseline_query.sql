-- Appendix-E baseline reportability query
-- Parameters: :tau
--
-- Purpose:
--   For every (config, axis) pair in the deployment context :tau, compute:
--     obs_count  — how many κ-qualifying observations exist (κ = H+M for baseline).
--     is_missing — 1 when obs_count = 0, meaning the cell is ⊥ under this κ-policy
--                  and the config CANNOT be reported on this axis.
--     lo / hi    — numeric range across qualifying observations (NULL if none or all
--                  observations are categorical).
--
-- Non-degenerate requirement (Appendix-E §2):
--   A config x is reportable for axis a iff is_missing = 0.
--   A config is FULLY reportable iff is_missing = 0 for ALL axes in the mandate set.
--   The query surfaces all axes (including those with no data) so the solver can
--   identify gaps and decide whether to promote, demote, or ⊥-fill the config.
--
-- Kappa fixed at H+M for baseline (P1).
--   Solver-side κ variation (e.g. κ = {H} only, or κ = {H,M,L}) is P4 work.
--   When κ changes, this query must be regenerated; do NOT patch the IN clause
--   by hand — generate via the solver's κ-policy registry instead.

SELECT
    c.id          AS config_id,
    a.axis        AS axis,
    COUNT(o.obs_id) AS obs_count,
    CASE WHEN COUNT(o.obs_id) = 0 THEN 1 ELSE 0 END AS is_missing,
    MIN(o.value_num) AS lo,
    MAX(o.value_num) AS hi
FROM config c
CROSS JOIN (
    -- Union of axes actually present in the DB with the P1 mandate set,
    -- so gaps in the mandate set are surfaced even if never observed.
    SELECT DISTINCT axis FROM observation
    UNION SELECT 'quality'
    UNION SELECT 'latency_p95'
    UNION SELECT 'throughput'
    UNION SELECT 'cost'
    UNION SELECT 'energy'
    UNION SELECT 'memory_hw'
    UNION SELECT 'governance'
    UNION SELECT 'reviewer_burden'
) AS a
LEFT JOIN observation o
    ON  o.config_id = c.id
    AND o.axis      = a.axis
    AND o.confidence IN ('H', 'M')
WHERE c.tau = :tau
GROUP BY c.id, a.axis
ORDER BY c.id, a.axis;
