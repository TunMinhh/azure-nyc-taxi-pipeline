# Setup and how to run

## Prerequisites

- Azure subscription (built and tested with Azure for Students)
- Azure Databricks workspace, **Premium** tier, with Unity Catalog
- Power BI Desktop (Windows) for the report

## 1. Azure resources (Portal)

Screenshots of each step are in [`docs/img/setup/`](img/setup/).

1. Resource group, region `eastasia`.   (Student Tier account doesn't allow to use SEA server)
2. Storage account: ADLS Gen2 (hierarchical namespace on), LRS, Hot, with containers `landing`, `bronze`, `silver`, `gold`.
3. Databricks workspace (Premium) and an **Access Connector for Azure Databricks**; grant the connector *Storage Blob Data Contributor* on the storage account.
4. In Databricks Catalog Explorer: a storage credential from the Access Connector, then one external location per container.
5. Budget alert on the subscription.

No account keys or SAS tokens are used anywhere; access goes through Unity Catalog and the managed identity.

## 2. Catalog and schemas

Run once in a SQL editor (replace `<storage>`):

```sql
CREATE CATALOG IF NOT EXISTS nyctaxi_dev
  MANAGED LOCATION 'abfss://landing@<storage>.dfs.core.windows.net/_catalog';

CREATE SCHEMA IF NOT EXISTS nyctaxi_dev.landing MANAGED LOCATION 'abfss://landing@<storage>.dfs.core.windows.net/files';
CREATE SCHEMA IF NOT EXISTS nyctaxi_dev.bronze  MANAGED LOCATION 'abfss://bronze@<storage>.dfs.core.windows.net/';
CREATE SCHEMA IF NOT EXISTS nyctaxi_dev.silver  MANAGED LOCATION 'abfss://silver@<storage>.dfs.core.windows.net/';
CREATE SCHEMA IF NOT EXISTS nyctaxi_dev.gold    MANAGED LOCATION 'abfss://gold@<storage>.dfs.core.windows.net/';
```

The notebooks create the volumes they need (`landing.raw_files`, `bronze.checkpoints`).

## 3. Code and compute

1. Workspace → **Create → Git folder** → this repository's URL.
2. Cluster: single node, `Standard_D4ds_v5`, Databricks Runtime 15.4 LTS, auto-termination 15 minutes.

## 4. Run the pipeline

Run the notebooks in order. Widgets (parameters) are at the top of each notebook.

| Notebook | Parameters | Result |
| --- | --- | --- |
| `01_land_files` | `catalog`, `sources` (`yellow,green,zones`), `start_month`, `end_month` | files in `/Volumes/<catalog>/landing/raw_files/<source>/` |
| `02_bronze` | `catalog`, `sources` | `bronze.yellow_trips_raw`, `bronze.green_trips_raw`, `bronze.taxi_zone_lookup_raw` |
| `03_silver` | `catalog`, `start_month`, `end_month` (empty = one month), `sources` (`yellow,green`) | `silver.trips`, `silver.trips_quarantine`, `silver.taxi_zones` |
| `04_gold` | `catalog` | `gold.fact_trip`, 6 dimensions, 2 views |

Example for the whole of 2025: `catalog = nyctaxi_dev`, `start_month = 2025-01`, `end_month = 2025-12`.

If `02_bronze` fails the first time a source gains a new column, run it again: Auto Loader updates the stored schema and continues (`addNewColumns` mode).

**Databricks Free Edition**: use `catalog = workspace`; everything else is the same.

## 5. Schedule it (Databricks Job)

Create a job `nyc_taxi_elt` with four notebook tasks chained `landing → bronze → silver → gold`, on an all-purpose cluster, with job parameters `catalog`, `start_month`, `end_month`. For a monthly run, set `start_month` to the new month and leave `end_month` empty.

## 6. Power BI

Connect Power BI Desktop to a Databricks SQL Warehouse (Get data → Azure Databricks → Import), load the Gold tables and the two location views, and create the relationships described in [Data model](../README.md#data-model-gold).