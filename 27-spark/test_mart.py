"""Integration test: duplicate rows/codes, cross-year months and ranking ties."""
import tempfile
from pathlib import Path
from pyspark.sql import SparkSession
from boston_mart import build_mart

spark = (SparkSession.builder.master("local[2]").appName("BostonMartTest")
         .config("spark.sql.shuffle.partitions", "2")
         .config("spark.sql.ansi.enabled", "false").getOrCreate())
spark.sparkContext.setLogLevel("ERROR")
try:
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        header = "INCIDENT_NUMBER,OFFENSE_CODE,DISTRICT,OCCURRED_ON_DATE,Lat,Long\n"
        row = "one,1,A,2017-01-01 01:00:00,42,-71\n"
        (root / "crime.csv").write_text(header + row + row +
            "one,0001,A,2017-01-01 01:00:00,42,-71\n" +
            "two,2,A,2017-01-02 01:00:00,44,-73\n"
            "three,1,A,2018-01-01 01:00:00,0,-1\n"
            "four,9,B,2018-01-02 01:00:00,41,-70\n"
            "five,1,,2018-01-02 01:00:00,41,-70\n"
            "six,1,A,invalid,41,-70\n", encoding="utf-8")
        (root / "codes.csv").write_text("CODE,NAME\n1,THEFT-A\n1,THEFT-B\n2,ASSAÚLT-X\n",encoding="ISO-8859-1")
        result, quality = build_mart(spark, str(root/"crime.csv"), str(root/"codes.csv"), "UTF-8", "ISO-8859-1")
        rows = {r.district:r.asDict() for r in result.collect()}
        assert quality == {"input_rows":8,"unique_rows":6,"valid_rows":4,"unmapped_codes_rows":1}, quality
        assert rows["A"]["crimes_total"] == 3
        assert rows["A"]["crimes_monthly"] == 1.5
        assert rows["A"]["frequent_crime_types"] == "THEFT, ASSAÚLT"
        assert rows["A"]["lat"] == 43 and rows["A"]["lng"] == -72
        assert rows["B"]["frequent_crime_types"] == "UNKNOWN"
        out = str(root/"mart")
        result.coalesce(1).write.parquet(out)
        assert spark.read.parquet(out).count() == 2
        assert len(list(Path(out).glob("*.parquet"))) == 1
        print("PASS: leading-zero code normalization before deduplication, Latin-1 dictionary, cleaning, dictionary deduplication, median, top types, coordinates and one Parquet part")
finally:
    spark.stop()
