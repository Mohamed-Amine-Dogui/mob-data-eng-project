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
#from pyspark.sql.functions import current_date
from pyspark.sql.types import StructType, StructField, StringType, IntegerType
from pyspark.sql.utils import AnalysisException

#from pyspark.sql import SQLContext

from delta.tables import DeltaTable


import time
import pandas as pd
from botocore.exceptions import BotoCoreError, ClientError

# Allow to display the hole pandas dataframe when we print
pd.set_option("display.max_columns", None)
pd.set_option("display.max_colwidth", None)
pd.set_option("display.width", None)

sys.path.insert(0, "/tmp/")

logger: Logger = logging.getLogger()
logger.setLevel(logging.INFO)


# Version of the glue job
__version__ = "0.4.0"

"""
The primary objective of this script is to read data from a
Delta table stored in an S3 bucket, process it using Apache Spark, and subsequently
create and populate a table in an AWS Glue Catalog located in a different AWS account (cross-account functionality).

Key Operations:
- Reads a Delta format table from an Amazon S3 bucket using Spark.
- Dynamically generates a DataFrame schema based on the Delta table.
- Assumes a cross-account IAM role to gain the necessary permissions for accessing
  resources in a separate AWS account where the target Glue Catalog resides.
- Creates a new table in the target AWS Glue Catalog (arn:aws:glue:eu-west-1:360928389411:database/datalicious ) using the schema derived from the
  DataFrame and writes the processed data.
- Glue Database: https://datahub.mpi-internal.com/manage-membership-and-access/groups/mobilede-ds-platform/glue
- Manages AWS sessions and uses temporary security credentials obtained through STS.

Note:
Ensure that the cross-account IAM role has adequate permissions and trust relationships
configured to allow the actions specified in this script. 
"""


def assume_role(role_arn, session_name):
    try:
        sts_client = boto3.client('sts')
        assumed_role = sts_client.assume_role(
            RoleArn=role_arn,
            RoleSessionName=session_name
        )
        logger.info(f"Successfully assumed role: {role_arn}")
        return assumed_role['Credentials']
    except ClientError as e:
        logger.error(f"Failed to assume role {role_arn}: {str(e)}")
        raise


def create_table_in_glue_catalog(glue_client, database_name, table_name, location, dataframe):
    """Creates a table in the Glue Catalog based on a DataFrame schema."""
    try:
        # Generate column list from DataFrame schema
        columns = [{'Name': field.name, 'Type': field.dataType.simpleString()} for field in dataframe.schema]

        # Log the schema details for testing and verification
        logger.info(f"Creating table with schema: {json.dumps(columns, indent=2)}")


        # Create the table using the dynamically generated columns
        glue_client.create_table(
            DatabaseName=database_name,
            TableInput={
                'Name': table_name,
                'StorageDescriptor': {
                    'Columns': columns,
                    'Location': location,
                    'InputFormat': 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat',
                    'OutputFormat': 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat',
                    'SerdeInfo': {
                        'SerializationLibrary': 'org.apache.hadoop.hive.serde2.lazy.LazySimpleSerDe',
                        'Parameters': {'serialization.format': '1'}
                    },
                },
                'TableType': 'EXTERNAL_TABLE',
                'Parameters': {'classification': 'parquet'}
            }
        )
        logger.info(f"Table {table_name} successfully created in database {database_name}")
    except Exception as e:
        logger.error(f"Failed to create table {table_name} in database {database_name}: {str(e)}")
        raise


def init_job(job_args: dict) -> Tuple[GlueContext, Job, logging.Logger]:
    """
    Initialize glue job
    :param job_args: Arguments
    :return: glue_context, job
    """
    # Initialize glue_context
    sc: SparkContext = SparkContext()
    glue_context: GlueContext = GlueContext(sc)

    # Initialize job
    job = Job(glue_context)
    job.init(job_args["JOB_NAME"], job_args)

    # Logger
    logger: logging.Logger = glue_context.get_logger()
    logger.info("Glue job '{}' started...".format(job_args["JOB_NAME"]))
    for key, value in job_args.items():
        logger.info(f"Parameter '{key}': {value}")

    return glue_context, job, logger


### TODO
if __name__ == "__main__":
    args = getResolvedOptions(
        sys.argv,
        [
            "JOB_NAME",
            "STAGE",
            "REGION"
        ],
    )

    gc, job, logger = init_job(args)


    stage = args["STAGE"]
    aws_region = args["REGION"]


    # build a spark session
    ss: SparkSession = gc.spark_session
    #ss = init_spark_session(credentials)

    s3_bucket = "mo-dev-glue-data-bucket/delta/ad_search/"
    target_s3_path = "s3a://mo-dev-glue-data-bucket/delta/ad_search/"
    datahub_region = "eu-west-1"
    glue_catalog_database_name = "datalicious"
    glue_catalog_table_name = "demo_table"

    deltaTable = DeltaTable.forPath(ss, target_s3_path)
    dataFrame = deltaTable.toDF()
    dataFrame.show(n=5)

    # Generate column list from DataFrame schema
    columns = [{'Name': field.name, 'Type': field.dataType.simpleString()} for field in dataFrame.schema]

    # Log the schema details for testing and verification
    logger.info(f"Creating table with schema: {json.dumps(columns, indent=2)}")

    # Assume the cross-account role
    role_arn = 'arn:aws:iam::360928389411:role/glue-job-role'
    credentials = assume_role(role_arn, 'GlueCrossAccountSession')

    # Create a session with assumed role credentials
    session = boto3.Session(
        aws_access_key_id=credentials['AccessKeyId'],
        aws_secret_access_key=credentials['SecretAccessKey'],
        aws_session_token=credentials['SessionToken'],
        region_name=datahub_region
    )

    # Create a Glue client using the assumed role credentials
    glue_client = session.client('glue')

    create_table_in_glue_catalog(glue_client,
                                 glue_catalog_database_name,
                                 glue_catalog_table_name,
                                 target_s3_path,
                                 dataFrame
                                 )

    job.commit()
