"""Build the Boston crime district mart using spark-submit."""
import argparse
from pyspark.sql import SparkSession, Window, functions as F


def build_mart(spark, crime_path, codes_path, crime_encoding="ISO-8859-1"):
    raw = (spark.read.option("header", True).option("encoding", crime_encoding)
           .option("mode", "FAILFAST").csv(crime_path))
    codes_raw = (spark.read.option("header", True).option("mode", "FAILFAST")
                 .csv(codes_path))
    required = {"INCIDENT_NUMBER", "OFFENSE_CODE", "DISTRICT", "OCCURRED_ON_DATE", "Lat", "Long"}
    if not required.issubset(raw.columns):
        raise ValueError(f"Missing crime columns: {sorted(required - set(raw.columns))}")
    if not {"CODE", "NAME"}.issubset(codes_raw.columns):
        raise ValueError("Offense dictionary must have CODE and NAME")

    unique = raw.dropDuplicates().cache()
    cleaned = (unique.select(
        F.trim("INCIDENT_NUMBER").alias("incident_number"),
        F.col("OFFENSE_CODE").cast("int").alias("code"),
        F.trim("DISTRICT").alias("district"),
        F.to_timestamp("OCCURRED_ON_DATE", "yyyy-MM-dd HH:mm:ss").alias("occurred_at"),
        F.col("Lat").cast("double").alias("raw_lat"),
        F.col("Long").cast("double").alias("raw_lng"))
        .filter("district IS NOT NULL AND district <> '' AND occurred_at IS NOT NULL "
                "AND incident_number IS NOT NULL AND incident_number <> '' AND code IS NOT NULL")
        .withColumn("lat", F.when(F.col("raw_lat").between(-90, 90) &
                                  ~F.col("raw_lat").isin(0, -1), F.col("raw_lat")))
        .withColumn("lng", F.when(F.col("raw_lng").between(-180, 180) &
                                  ~F.col("raw_lng").isin(0, -1), F.col("raw_lng")))
        .cache())
    codes = (codes_raw.select(F.col("CODE").cast("int").alias("code"), F.trim("NAME").alias("name"))
             .filter("code IS NOT NULL AND name IS NOT NULL AND name <> ''")
             .groupBy("code").agg(F.min("name").alias("name")))
    joined = (cleaned.join(codes, "code", "left")
              .withColumn("crime_type", F.coalesce(F.trim(F.split("name", "-").getItem(0)), F.lit("UNKNOWN"))))
    totals = cleaned.groupBy("district").agg(
        F.count("*").alias("crimes_total"), F.avg("lat").alias("lat"), F.avg("lng").alias("lng"))
    monthly = (cleaned.withColumn("year_month", F.date_format("occurred_at", "yyyy-MM"))
               .groupBy("district", "year_month").count()
               .groupBy("district").agg(F.expr("percentile(count, 0.5)").alias("crimes_monthly")))
    ranked = (joined.groupBy("district", "crime_type").count()
               .withColumn("rank", F.row_number().over(
                   Window.partitionBy("district").orderBy(F.desc("count"), F.asc("crime_type"))))
               .filter("rank <= 3"))
    top = ranked.groupBy("district").agg(F.concat_ws(", ", F.transform(
        F.sort_array(F.collect_list(F.struct("rank", "crime_type"))),
        lambda item: item["crime_type"])).alias("frequent_crime_types"))
    metrics = {"input_rows": raw.count(), "unique_rows": unique.count(),
               "valid_rows": cleaned.count(), "unmapped_codes_rows": joined.filter("name IS NULL").count()}
    result = (totals.join(monthly, "district").join(top, "district")
              .select("district", "crimes_total", "crimes_monthly", "frequent_crime_types", "lat", "lng")
              .orderBy("district"))
    return result, metrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("crime_path")
    parser.add_argument("codes_path")
    parser.add_argument("output_path")
    parser.add_argument("--crime-encoding", default="ISO-8859-1")
    args = parser.parse_args()
    spark = (SparkSession.builder.appName("BostonCrimeMart")
             .config("spark.sql.session.timeZone", "UTC")
             .config("spark.sql.ansi.enabled", "false")
             .config("spark.sql.legacy.timeParserPolicy", "CORRECTED").getOrCreate())
    spark.sparkContext.setLogLevel("WARN")
    try:
        mart, metrics = build_mart(spark, args.crime_path, args.codes_path, args.crime_encoding)
        print("QUALITY_METRICS", metrics)
        mart.show(truncate=False)
        mart.coalesce(1).write.mode("errorifexists").parquet(args.output_path)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
