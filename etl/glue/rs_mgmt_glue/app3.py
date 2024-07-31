import logging
from logging import Logger
import os
import sys
from datetime import datetime, timedelta
from typing import Tuple
import json

import boto3
from awsglue import DynamicFrame
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as f
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, DateType, TimestampType
from pyspark.sql.utils import AnalysisException

from delta.tables import DeltaTable

import time
import pandas as pd
from botocore.exceptions import BotoCoreError, ClientError

pd.set_option("display.max_columns", None)
pd.set_option("display.max_colwidth", None)
pd.set_option("display.width", None)

sys.path.insert(0, "/tmp/")

logger: Logger = logging.getLogger()
logger.setLevel(logging.INFO)

__version__ = "0.4.0"

def replace_with_dummy_values(df: DataFrame) -> DataFrame:
    for col in df.columns:
        data_type = df.schema[col].dataType
        if isinstance(data_type, (StringType, IntegerType)):
            df = df.withColumn(col, f.lit("dummy_value") if isinstance(data_type, StringType) else f.lit(0))
    return df


def reconstruct_delta_table(ss, delta_table_path, target_s3_path):
    try:
        if not target_s3_path.endswith('/'):
            target_s3_path += '/'

        parquet_files = f"{delta_table_path}/date=*/part-*.parquet"

        # Read the data ignoring the Delta log, focusing on all Parquet files found with the pattern
        df = ss.read.format("parquet").load(parquet_files)

        # Write back to a new location as a Delta table, partitioning by the ingestion_date column
        df.write.format("delta").partitionBy("ingestion_date").mode("overwrite").save(target_s3_path)

        logger.info(f"New Delta table created at {target_s3_path} partitioned by ingestion_date. Please verify and replace the old table.")
    except Exception as e:
        logger.error(f"Error during table reconstruction: {str(e)}")


def create_dummy_delta_table(ss, delta_table_path, dummy_table_path):
    try:
        if not dummy_table_path.endswith('/'):
            dummy_table_path += '/'

        df = ss.read.format("delta").load(delta_table_path)
        df = replace_with_dummy_values(df)

        df.write.format("delta").mode("overwrite").save(dummy_table_path)
        logger.info(f"Dummy Delta table created at {dummy_table_path}.")
    except Exception as e:
        logger.error(f"Error during table creation: {str(e)}")

def spark_read_delta_df(ss, delta_table_path):
    try:
        logger.info(f"Attempting to read from S3 path: {delta_table_path}")
        df = ss.read.format("delta").load(delta_table_path)
        return df
    except AnalysisException as e:
        logger.error(f"AnalysisException: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return None

def init_job(job_args: dict) -> Tuple[GlueContext, Job, logging.Logger]:
    sc: SparkContext = SparkContext()
    glue_context: GlueContext = GlueContext(sc)

    job = Job(glue_context)
    job.init(job_args["JOB_NAME"], job_args)

    logger: logging.Logger = glue_context.get_logger()
    logger.info("Glue job '{}' started...".format(job_args["JOB_NAME"]))
    for key, value in job_args.items():
        logger.info(f"Parameter '{key}': {value}")

    return glue_context, job, logger

if __name__ == "__main__":
    args = getResolvedOptions(
        sys.argv,
        [
            "JOB_NAME",
            "TARGET_BUCKET_NAME",
            "STAGE",
            "REGION",
        ],
    )

    gc, job, logger = init_job(args)

    target_bucket_name = args["TARGET_BUCKET_NAME"]
    stage = args["STAGE"]
    aws_region = args["REGION"]

    ss: SparkSession = gc.spark_session

    s3_bucket = "mo-delta-ad-search-events-730335331410-eu-central-1/ad_search/"
    delta_table_path = "s3a://mo-delta-ad-search-events-730335331410-eu-central-1/ad_search/"

    target_s3_path= "s3a://mo-dev-glue-data-bucket/delta/ad_search/"
    reconstruct_delta_table(ss, delta_table_path, target_s3_path)

    deltaTable = DeltaTable.forPath(ss, target_s3_path)
    deltaTable.toDF().show()

    #dummy_table_path = "s3a://mo-dev-glue-data-bucket/delta/dummy_ad_search/"
    #create_dummy_delta_table(ss, delta_table_path, dummy_table_path)

    #deltaTable = DeltaTable.forPath(ss, dummy_table_path)
    #deltaTable.toDF().show()

    job.commit()
