# Data exploration and quality

Profiling was done on yellow 2025-01 (3,475,226 rows) and green 2025-01 (48,326 rows). The findings below drove the Silver rules.

## Findings

1. **Null is not always an error.** 540,149 yellow rows (15.5%) have `payment_type = 0` (Flex Fare) and five columns null at once (`passenger_count`, `RatecodeID`, `store_and_fwd_flag`, `congestion_surcharge`, `Airport_fee`). They are real trips, so they are kept. Green encodes the same cluster as `payment_type = NULL` instead of `0`.
2. **Negative totals are reversal entries, not trips.** 63,037 rows have `total_amount < 0`. 59,609 of them pair with an original trip on vendor + pickup time + dropoff time + pickup zone + negated fare. The drop-off zone often differs by one neighbouring zone, and the payment type can change (cash trip later disputed), so neither is part of the match key.
3. **Some Flex Fare amounts are meaningless.** About 81k rows have `fare_amount < 0` (fixed −4.75 / −4.0 / −1.5) with a small positive total. Median total is $3.00 for trips under 2 miles and $6.17 for trips over 10 miles, compared with $15.69 and $53.95 for normal Flex Fare trips. Distance and duration look valid, so the trips are kept but their money is excluded from revenue.
4. **Summing money columns double counts.** In 32% of valid rows the components do not add up to `total_amount`. VendorID 1 already includes the congestion and CBD fees in `extra` while also reporting them in their own columns. Revenue therefore always uses `total_amount`.
5. **Outliers are rare but loud.** Only 122 trips exceed 200 miles (max 276,423), yet they raise the average distance from 3.17 to 6.02 miles.
6. **Month edges are real.** 22 trips in the January file start on the evening of Dec 31 or just after midnight on Feb 1. Trips up to one day outside the file month are kept.
7. **Schema is stable in 2025.** Auto Loader's `_rescued_data` is empty for all 12 yellow files.
8. **One vendor drives the duration rejects (found in the full-year run).** Rules were set on January, where `invalid_trip_duration` was 0.09% of yellow trips. Over 2025 it reached 561,220 rows (1.15%), rising from 3,254 in January to 56k–70k per month from May on. Splitting the rejects shows two separate problems:
    - **Duration ≤ 0: 536k rows, 98% from VendorID 7 (Helix).** The count grows month by month, which points to a change in how this provider records timestamps rather than to driver behaviour.
    - **Duration > 6 hours: about 1.2k rows every month, mostly VendorID 2.** The median is 1,408 minutes (23.5 hours) and the 90th percentile 1,437 minutes, so these are almost always a drop-off stamped on the next day or a meter left running.

    The quarantine table made this visible: the rows were not silently dropped, and a single `groupBy` on `dq_reason`, month and vendor explained them.

## Silver rules

`dq_reason` is the first rule that matches; `null` means the row is valid.

| Order | `dq_reason` | Rejects when | Yellow 2025-01 | Yellow 2025 | Green 2025 |
| --- | --- | --- | ---: | ---: | ---: |
| 1 | `schema_mismatch` | `_rescued_data` is not null | 0 | 0 | 0 |
| 2 | `missing_file_month_or_pickup_ts` | file month or pickup time is missing | 0 | 0 | 0 |
| 3 | `pickup_outside_file_month` | pickup is more than 1 day outside the file's month | 0 | 8 | 76 |
| 4 | `invalid_trip_duration` | null, ≤ 0 or > 360 minutes | 3,254 | 561,220 | 4,383 |
| 5 | `invalid_trip_distance` | null, ≤ 0 or > 200 miles | 90,302 | 1,388,886 | 24,107 |
| 6 | `missing_total_amount` | total is null | 0 | 0 | 0 |
| 7 | `negative_total_amount_review` | total < 0 (reversal entry) | 58,498 | 900,751 | 1,062 |

Valid rows: yellow 2025-01 **3,323,172 (95.6%)**; full year **45,871,737 (94.15%)** yellow and **561,747 (94.99%)** green.

The yearly rate of `invalid_trip_duration` (1.15% of yellow) is far higher than in January (0.09%); see finding 8. Deliberately **not** rejected: null or odd `passenger_count` (driver-entered; Gold measures use 1–6 only), null `payment_type` in green, zones 264/265 (Unknown / Outside NYC), and negative fares with a non-negative total.

Field definitions: [docs/data-dict.md](data-dict.md).