# NYC Taxi Lakehouse on Azure Databricks

A config-driven Medallion pipeline that ingests NYC TLC yellow and green taxi trips (2025) into Delta Lake on Azure Databricks, applies explicit data-quality rules with a quarantine table, and models the result as a star schema for Power BI.

![Power BI overview](docs/img/dashboard_overview.png)

## Architecture

![Architecture](docs/img/architecture.png)

| Layer | What it holds | How it is written |
| --- | --- | --- |
| Landing | Original TLC files in the Unity Catalog volume `landing.raw_files` | Download only missing files |
| Bronze | Delta tables with the source schema + `_source_file`, `_ingestion_time` | Auto Loader, exactly once per file |
| Silver | `trips` (yellow + green, one typed schema), `trips_quarantine`, `taxi_zones` | Delta `MERGE` / `replaceWhere` per taxi type × month |
| Gold | Star schema: `fact_trip` + 6 dimensions | Overwrite, with integrity checks |

**Tech stack:** Azure Databricks (Unity Catalog) · ADLS Gen2 · PySpark · Delta Lake · Auto Loader · Power BI

## Data model (Gold)
 
![Star schema](docs/img/star_schema.png)
 
`fact_trip` has one row per valid trip. It holds keys and measures only; Power BI resolves the joins through relationships.

## Repository layout

```
config/            sources.yml, dimensions.yml
src/nyctaxi/       landing.py, bronze.py, silver.py, gold.py   (all logic)
notebooks/         01_land_files → 02_bronze → 03_silver → 04_gold   (thin shells)
tests/             pytest suite for src/ (local Spark, no Databricks needed)
.github/workflows/ CI: runs the tests on every push and pull request
docs/              setup, data quality, data dictionary
```

## Quick start

1. Create the Azure resources, catalog and schemas: [docs/setup.md](docs/setup.md).
2. Add this repo as a Git folder in Databricks.
3. Run the notebooks in order with `catalog = nyctaxi_dev`, `start_month = 2025-01`, `end_month = 2025-12`.

P/S: the notebook's default catalog is `workspace` due to test run on Databricks Free Edition, remember to change it to your catalog before running 

## Tests

Unit tests cover the transform logic in `src/` (DQ rules, duplicates, trip_id, star schema keys, revenue) on a local Spark session. Requires Python 3.11+ and Java 17.

```bash
pip install -r requirements-dev.txt
pytest -v
```

GitHub Actions runs the same tests on every push and pull request.

## Documentation

| Document | Content |
| --- | --- |
| [Setup and how to run](docs/setup.md) | Azure resources, catalog SQL, cluster, notebook parameters, job, Power BI |
| [Data exploration and quality](docs/data_quality.md) | Profiling findings and the Silver rules with reject counts |
| [Data dictionary](docs/data-dict.md) | TLC field definitions |

## Result

Full year 2025 on Azure Databricks (12 monthly files per taxi type), run by the job `nyc_taxi_elt`.

| | Yellow | Green |
| --- | ---: | ---: |
| Bronze rows | 48,722,602 | 591,375 |
| Rows with schema mismatch (`_rescued_data`) | 0 | 0 |
| Silver valid rows | 45,871,737 | 561,747 |
| Quarantined rows | 2,850,865 | 29,628 |
| Pass rate | 94.15% | 94.99% |

![Lineage](docs/img/lineage.png)
![Databrick Jobs](docs/img/databrick_jobs.png)

## Limitations

- **Revenue is slightly overstated (~1.7%).** Some trips have a reversal entry (a row with negative `total_amount`). The reversal goes to quarantine, but the original trip stays in `fact_trip` and still counts as revenue. Estimated on yellow 2025-01; the fix is an `is_reversed` flag (matching on vendor, pickup, dropoff, pickup zone and opposite fare).
- **Flex Fare rows with a negative fare have revenue = 0.** Their money columns do not add up, so they count as trips but not as revenue.
- **One vendor is under-represented.** About 536k trips with duration ≤ 0 are quarantined; 98% of them come from VendorID 7, so its trips are undercounted.
- **Gold is rebuilt in full on every run.** Fine at ~46M rows; an incremental MERGE by month would be needed at larger scale.
- **Notebooks and Auto Loader are not unit-tested.** CI tests the logic in `src/` on a local Spark; the Databricks-only parts (Auto Loader, Unity Catalog views, notebook wiring) are checked by the job run and the assertions in the notebooks.

## Data source

[NYC Taxi & Limousine Commission trip record data](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page).