from pyspark.sql import functions as F
from pyspark.sql import DataFrame, SparkSession

def read_stream(spark: SparkSession, source_dir: str, checkpoint_dir: str, source_format: str, glob_filter: str | None = None) -> DataFrame:   
    reader = (spark.readStream
        .format("cloudFiles")
        .option("cloudFiles.format", source_format)
        .option("cloudFiles.schemaLocation", f"{checkpoint_dir}/_schema")
        .option("pathGlobFilter", glob_filter or f"*.{source_format}")
    )

    if source_format == "csv":
        reader = reader.option("header", True)
    
    df = reader.load(source_dir)

    df_bronze = (df
                .withColumn("_source_file", F.expr("_metadata.file_path"))      
                .withColumn("_ingestion_time", F.current_timestamp())
                )
    return df_bronze
    
def write_stream(df_bronze: DataFrame, checkpoint_dir: str, table: str) -> int:
    query = (df_bronze.writeStream
    .option("checkpointLocation", f"{checkpoint_dir}/_checkpoint")  
    .option("mergeSchema", "true")                                  # let table add new column
    .trigger(availableNow=True)                                     # stop the stream when all data is processed or it will run and wait for new data 
    .toTable(table))

    query.awaitTermination()

    return sum((p["numInputRows"] or 0) for p in query.recentProgress)