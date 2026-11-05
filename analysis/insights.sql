-- Q1. How many pickup zones generate 80% of revenue?
-- Result: 35 of 259 zones (13.5%). Unknown and outside-NYC zones are excluded.
WITH z AS (
  SELECT pu.zone, SUM(f.revenue) AS revenue
  FROM workspace.gold.fact_trip f
  JOIN workspace.gold.dim_location pu ON f.pickup_location_id = pu.location_id
  WHERE f.pickup_location_id NOT IN (-1, 264, 265)
  GROUP BY pu.zone
),
r AS (
  SELECT revenue,
         ROW_NUMBER() OVER (ORDER BY revenue DESC) AS zone_rank,
         COUNT(*) OVER () AS total_zones,
         SUM(revenue) OVER (ORDER BY revenue DESC) / SUM(revenue) OVER () AS cumulative_share
  FROM z
)
SELECT MIN(zone_rank) AS zones_for_80pct_revenue,
       MAX(total_zones) AS total_zones
FROM r
WHERE cumulative_share >= 0.8;


-- Q3. Which routes generate the most revenue?
-- Result: 8 of the top 10 routes involve an airport. JFK -> Times Sq leads with $7.9M.
-- Upper East Side South -> North has 3.5x its trips but only $4.6M.
SELECT pu.zone AS pickup_zone, dr.zone AS dropoff_zone,
       COUNT(*) AS trips,
       ROUND(SUM(f.revenue), 0) AS revenue,
       ROUND(100.0 * SUM(f.revenue) / SUM(SUM(f.revenue)) OVER (), 2) AS revenue_share_pct
FROM workspace.gold.fact_trip f
JOIN workspace.gold.dim_location pu ON f.pickup_location_id = pu.location_id
JOIN workspace.gold.dim_location dr ON f.dropoff_location_id = dr.location_id
WHERE f.pickup_location_id NOT IN (-1, 264, 265)
  AND f.dropoff_location_id NOT IN (-1, 264, 265)
GROUP BY pu.zone, dr.zone
ORDER BY revenue DESC
LIMIT 10;



-- Q5. How do trips and revenue change by month?
-- Result: May has the most trips (4.34M). December has the highest revenue ($128.3M) and revenue per trip ($31.32), with average distance almost unchanged.
SELECT d.month,
       COUNT(*) AS trips,
       ROUND(SUM(f.revenue), 0) AS revenue,
       ROUND(AVG(f.revenue), 2) AS revenue_per_trip,
       ROUND(AVG(f.trip_distance), 2) AS avg_distance
FROM workspace.gold.fact_trip f
JOIN workspace.gold.dim_date d ON f.pickup_date_id = d.date_id
WHERE d.year = 2025
GROUP BY d.month
ORDER BY d.month;


-- Q6. Which weekday and hour combinations are busiest?
-- Result: all top 10 fall on Wednesday, Thursday or Saturday between 17:00 and 23:00.
-- Thursday 18:00 is the busiest, with 484,441 trips.
SELECT d.day_name, t.hour,
       COUNT(*) AS trips,
       ROUND(AVG(f.revenue), 2) AS revenue_per_trip
FROM workspace.gold.fact_trip f
JOIN workspace.gold.dim_date d ON f.pickup_date_id = d.date_id
JOIN workspace.gold.dim_time t ON f.pickup_time_id = t.time_id
WHERE d.year = 2025
GROUP BY d.day_name, t.hour
ORDER BY trips DESC
LIMIT 10;


-- Q7. How much is revenue overstated by reversed trips?
-- Result: an estimated 750,951 trips (1.62%) and $22.6M (1.76% of revenue).
-- Matching is approximate: vendor, pickup, dropoff, pickup zone and opposite fare.
WITH reversals AS (
  SELECT DISTINCT taxi_type, vendor_id, pickup_ts, dropoff_ts, pu_location_id,
         -fare_amount AS original_fare
  FROM workspace.silver.trips_quarantine
  WHERE total_amount < 0
),
flagged AS (
  SELECT t.taxi_type,
         CASE WHEN t.fare_amount >= 0 THEN t.total_amount ELSE 0 END AS revenue,
         r.taxi_type IS NOT NULL AS is_reversed
  FROM workspace.silver.trips t
  LEFT JOIN reversals r
    ON  t.taxi_type      = r.taxi_type
    AND t.vendor_id      = r.vendor_id
    AND t.pickup_ts      = r.pickup_ts
    AND t.dropoff_ts     = r.dropoff_ts
    AND t.pu_location_id = r.pu_location_id
    AND t.fare_amount    = r.original_fare
)
SELECT COALESCE(taxi_type, 'total') AS taxi_type,
       COUNT(*) AS trips,
       SUM(CASE WHEN is_reversed THEN 1 ELSE 0 END) AS reversed_trips,
       ROUND(100.0 * SUM(CASE WHEN is_reversed THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_trips,
       ROUND(SUM(revenue), 0) AS revenue,
       ROUND(SUM(CASE WHEN is_reversed THEN revenue ELSE 0 END), 0) AS reversed_revenue,
       ROUND(100.0 * SUM(CASE WHEN is_reversed THEN revenue ELSE 0 END) / SUM(revenue), 2) AS pct_revenue
FROM flagged
GROUP BY ROLLUP (taxi_type);


-- Q8. Which vendor causes zero or negative durations?
-- Result: VendorID 7 accounts for 535,901 of 548,214 rows (97.75%), yellow and green combined.
SELECT vendor_id,
       COUNT(*) AS invalid_trips,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS share_pct
FROM workspace.silver.trips_quarantine
WHERE dq_reason = 'invalid_trip_duration'
  AND trip_duration_min <= 0
GROUP BY vendor_id
ORDER BY invalid_trips DESC;
