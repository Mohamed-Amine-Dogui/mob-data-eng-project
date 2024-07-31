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

def fetch_schema(ss: SparkSession, glue_database: str, glue_table: str):
    client = boto3.client('glue')
    try:
        response = client.get_table(DatabaseName=glue_database, Name=glue_table)
        columns = response['Table']['StorageDescriptor']['Columns']

        schema_data = [(col['Name'], col['Type']) for col in columns]
        schema = StructType([
            StructField("column_name", StringType(), True),
            StructField("column_type", StringType(), True)
        ])
        df = ss.createDataFrame(schema_data, schema)
        return df
    except Exception as e:
        logger.error(f"Failed to fetch schema from Glue Catalog: {str(e)}")
        return None

def fetch_schema_external(database_name, external_schema_name, glue_catalog_table_name, workgroup_name, secret_arn, ss):
    redshift_data_client = boto3.client('redshift-data')
    fetch_query = f"""
    SELECT columnname, external_type
    FROM SVV_EXTERNAL_COLUMNS
    WHERE schemaname = '{external_schema_name}'
    AND tablename = '{glue_catalog_table_name}';
    """
    try:
        response = redshift_data_client.execute_statement(
            Database=database_name,
            Sql=fetch_query,
            WorkgroupName=workgroup_name,
            SecretArn=secret_arn
        )
        query_id = response['Id']

        # Wait for query to finish
        while True:
            status_response = redshift_data_client.describe_statement(Id=query_id)
            status = status_response['Status']
            logger.info(f"Query {query_id} status: {status}")
            if status == "FINISHED":
                logger.info(f"Query {query_id} completed successfully.")
                break
            elif status in ["FAILED", "ABORTED"]:
                error_message = (f"Message error can not be displayed please go to the Redshift query editor and run following "
                                 f"\nquery: {fetch_query} "
                                 f"\nin this "
                                 f"\nRedshift_Workgroup: {workgroup_name} "
                                 f"\nRedshift_Database: {database_name}")
                if 'Error' in status_response and 'Message' in status_response['Error']:
                    error_message = status_response['Error']['Message']
                logger.error(f"Query {query_id} failed: {error_message}")
                raise Exception(f"Query failed: {error_message}")
            time.sleep(5)  # Delay to prevent throttling

        result = redshift_data_client.get_statement_result(Id=query_id)
        records = [(record[0]['stringValue'], record[1]['stringValue']) for record in result['Records']]

        schema = StructType([
            StructField("column_name", StringType(), True),
            StructField("column_type", StringType(), True)
        ])

        df = ss.createDataFrame(records, schema)
        return df
    except Exception as e:
        logger.error(f"Error executing query inside fetch_schema_external(): {str(e)}")
        raise


def df_from_catalog(glue_catalog_database_name, glue_catalog_table_name, gc):
    try:
        # Create DataFrame from Glue Catalog
        read_df = gc.create_dynamic_frame.from_catalog(
            database=glue_catalog_database_name,
            table_name=glue_catalog_table_name,
            additional_options={
                "useSparkDataSource": True,
                # Include any other options
            }
        ).toDF()
        return read_df
    except Exception as e:
        logger.error(f"An error occurred in df_from_catalog(): {str(e)}")
        return None


def calc_max_length_df(ss, catalog_df, fetch_schema_df, buffer_percent=20):
    # Filter to include only string columns
    string_columns = fetch_schema_df.filter(fetch_schema_df['column_type'] == 'string').select('column_name')
    string_column_list = [row.column_name for row in string_columns.collect()]

    # Select string columns and calculate maximum length
    string_df = catalog_df.select([f.col(c).alias(c) for c in string_column_list])
    max_lengths = string_df.agg(*(f.max(f.length(f.col(c))).alias(c) for c in string_column_list)).collect()[0]

    default_length = 255  # Default max length if actual length is None
    max_lengths_with_buffer = {}
    for col, length in max_lengths.asDict().items():
        if length is None:
            length = default_length
        max_length_with_buffer = int(round(length + (length * buffer_percent / 100)))
        max_lengths_with_buffer[col] = max_length_with_buffer

    max_lengths_df =ss.createDataFrame(
        [(col, max_len) for col, max_len in max_lengths_with_buffer.items()],
        schema=["column_name", "max_length"]
    )
    return max_lengths_df


def create_table_query(ss, catalog_df, fetch_schema_df, max_length_df, redshift_schema_name, redshift_table_name):
    try:
        column_order = {name: idx for idx, name in enumerate(catalog_df.columns)}
        order_df = ss.createDataFrame(list(column_order.items()), ["column_name", "order_index"])

        # Join fetch_schema_df with max_length_df on the column name
        enhanced_schema_df = fetch_schema_df.join(
            max_length_df,
            on="column_name",
            how="left"
        )

        # Join with the order DataFrame to get order indices
        enhanced_schema_df = enhanced_schema_df.join(
            order_df,
            on="column_name",
            how="left"
        )
        # Sort by the order index
        enhanced_schema_df = enhanced_schema_df.orderBy("order_index").drop("order_index")

        # Generate SQL for creating the table
        create_table_columns = []
        for row in enhanced_schema_df.collect():
            column_name = row['column_name']
            column_type = row['column_type']
            max_length = row['max_length']

            if column_type.startswith('string'):
                redshift_type = f'VARCHAR({max_length})' if max_length else 'VARCHAR(255)'
            elif column_type == 'int':
                redshift_type = 'INTEGER'
            elif column_type == 'timestamp':
                redshift_type = 'TIMESTAMP'
            elif column_type == 'boolean':
                redshift_type = 'BOOLEAN'
            elif column_type.startswith('double'):
                redshift_type = 'DOUBLE PRECISION'
            elif column_type.startswith('array'):
                redshift_type = 'SUPER'
            else:
                redshift_type = 'VARCHAR(255)'
            create_table_columns.append(f"{column_name} {redshift_type}")

        columns_sql = ",\n".join(create_table_columns)
        create_table_sql = f"""
        CREATE SCHEMA IF NOT EXISTS {redshift_schema_name};
        CREATE TABLE IF NOT EXISTS {redshift_schema_name}.{redshift_table_name} (
            {columns_sql}
        );
        """
        return create_table_sql
    except Exception as e:
        logger.error(f"Error generating create table statement: {str(e)}")
        raise


def execute_rs_query(query, database_name, workgroup_name, secret_arn):
    redshift_data_client = boto3.client('redshift-data')
    try:
        logger.info(f"Executing query: {query}")
        response = redshift_data_client.execute_statement(
            Database=database_name,
            Sql=query,
            WorkgroupName=workgroup_name,
            SecretArn=secret_arn
        )
        query_id = response['Id']
        logger.info(f"Query submitted, ID: {query_id}")

        while True:
            status_response = redshift_data_client.describe_statement(Id=query_id)
            status = status_response['Status']
            logger.info(f"Query {query_id} status: {status}")
            if status in ["FINISHED"]:
                logger.info(f"Query {query_id} completed successfully.")
                break
            elif status in ["FAILED", "ABORTED"]:
                error_message = (f"Message error can not be displayed please go to the Redshift query editor and run following "
                                 f"\nquery: {query} "
                                 f"\nin this "
                                 f"\nRedshift_Workgroup: {workgroup_name} "
                                 f"\nRedshift_Database: {database_name}")
                if 'Error' in status_response and 'Message' in status_response['Error']:
                    error_message = status_response['Error']['Message']
                logger.error(f"Query {query_id} failed: {error_message}")
                raise Exception(f"Query failed: {error_message}")

            time.sleep(5)  # Delay to prevent throttling

        return query_id
    except Exception as e:
        logger.error(f"Error executing query: {str(e)}")
        raise

def get_secret_arn(secret_name, sm_client):
    try:
        response = sm_client.describe_secret(SecretId=secret_name)
        return response['ARN']
    except ClientError as e:
        logger.error(f"Error retrieving secret ARN: {str(e)}")
        raise e


def load_to_redshift(df: DataFrame, database_name: str, redshift_username: str, redshift_password: str, schema_name: str, target_table: str, connection_url: str, gc: GlueContext, target_s3_path: str):
    try:
        temp_dir = os.path.join(target_s3_path, "tmp")
        table = f"{schema_name}.{target_table}"

        dynamic_frame = DynamicFrame.fromDF(df, gc, "dynamic_frame_for_redshift")

        connection_options = {
            "url": f"{connection_url}/{database_name}",
            "user": redshift_username,
            "password": redshift_password,
            "dbtable": table,
            "redshiftTmpDir": temp_dir,
        }

        gc.write_dynamic_frame.from_options(
            frame=dynamic_frame,
            connection_type="redshift",
            connection_options=connection_options
        )

        logger.info("Data loaded to Redshift table successfully.")

    except ClientError as e:
        logger.error(f"AWS ClientError occurred: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"An error occurred during data load to Redshift: {str(e)}")
        raise


def wait_for_query_completion(redshift_data_client, query_id):
    while True:
        response = redshift_data_client.describe_statement(Id=query_id)
        status = response['Status']
        if status in ['FINISHED', 'FAILED', 'ABORTED']:
            return status
        time.sleep(10)

def read_from_redshift_df(
        query,
        connection_name,
        target_s3_path,
        table_name,
        gc
):
    try:
        tmp_dir = os.path.join(target_s3_path, "tmp", table_name)
        connection_options = {
            "sampleQuery": query,
            "redshiftTmpDir": tmp_dir,
            "useConnectionProperties": "true",
            "connectionName": connection_name,
        }
        logger.info(f"Connecting to Redshift with options: {connection_options}")

        df = gc.create_dynamic_frame_from_options(connection_type="redshift", connection_options=connection_options).toDF()

        if df:
            logger.info(f"Connection to Redshift established successfully.")
        else:
            logger.warning(f"Connection to Redshift was successful, but no data was returned.")

        return df
    except Exception as e:
        logger.error(f"Error connecting to Redshift: {e}")
        raise ConnectionError("Failed to connect to Redshift.") from e

def query_to_pandas_df(database_name, workgroup_name, secret_arn, query, keys):
    redshift_data_client = boto3.client('redshift-data')

    try:
        statement = redshift_data_client.execute_statement(
            Database=database_name,
            Sql=query,
            WorkgroupName=workgroup_name,
            SecretArn=secret_arn
        )
        query_id = statement.get("Id")

        # Adjusted the sleep time to reduce rapid API calls
        while True:
            status_response = redshift_data_client.describe_statement(Id=query_id)
            status = status_response.get("Status")
            if status == "FINISHED":
                break
            elif status in ["FAILED", "ABORTED"]:
                raise Exception(f"Query failed or aborted: {status_response}")
            time.sleep(1)
            print("Waiting for query completion...")

        result = redshift_data_client.get_statement_result(Id=query_id)
    except ClientError as e:
        logger.error(f"Redshift Data API client error: {str(e)}")
        raise e
    except Exception as e:
        logger.error(f"Error executing query: {str(e)}")
        raise

    rows = []
    for record in result["Records"]:
        values = []
        for item in record:
            if item.get("stringValue") is not None:
                values.append(item.get("stringValue"))
            elif item.get("longValue") is not None:
                values.append(item.get("longValue"))
            elif item.get("doubleValue") is not None:
                values.append(item.get("doubleValue"))
            elif item.get("booleanValue") is not None:
                values.append(item.get("booleanValue"))
            elif item.get("isNull"):
                values.append(None)
        row_dict = dict(zip(keys, values))
        rows.append(row_dict)

    pandas_df = pd.DataFrame.from_dict(rows)

    return pandas_df


def refresh_delta_table(ss, table_path):
    try:
        # Load the Delta table
        deltaTable = DeltaTable.forPath(ss, table_path)

        # Generate manifest to force a consistency check
        deltaTable.generate("symlink_format_manifest")

        # Perform a full refresh
        ss.sql(f"REFRESH TABLE delta.`{table_path}`")
        logger.info("Table refreshed successfully.")
    except Exception as e:
        logger.error(f"Error during table refresh: {str(e)}")


def reconstruct_delta_table(ss, delta_table_path, target_s3_path):
    try:
        if not target_s3_path.endswith('/'):
            target_s3_path += '/'

            # path = "mo-delta-ad-search-events/svc-ad-search/date=2019-04-01/part-00095-4724d8cb-4732-4597-a61f-dd913b59301e.c000.snappy.parquet"
            #
            # h = "s3://dl-mobilede-ds-platform-pro-datalake-xgukef6on6j2/mo-delta-ad-search-events/svc-ad-search"

        parquet_files = f"{delta_table_path}/date=*/part-*.parquet"

        # Read the data ignoring the Delta log, focusing on all Parquet files found with the pattern
        df = ss.read.format("parquet").load(parquet_files)

        new_table_path = f"{target_s3_path}new_delta_table/"
        # Write back to a new location as a Delta table, partitioning by the ingestion_date column
        df.write.format("delta").partitionBy("ingestion_date").mode("overwrite").save(new_table_path)

        logger.info(f"New Delta table created at {new_table_path} partitioned by ingestion_date. Please verify and replace the old table.")
    except Exception as e:
        logger.error(f"Error during table reconstruction: {str(e)}")


def spark_read_delta_df(ss, delta_table_path):
    try:
        # Invalidate cache first if needed
        #ss.sql(f"REFRESH TABLE delta.`{delta_table_path}`")

        logger.info(f"Attempting to read from S3 path: {delta_table_path}")
        df = ss.read.format("delta").load(delta_table_path)
        return df
    except AnalysisException as e:
        logger.error(f"AnalysisException: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return None


def load_to_redshift_with_connector(df: DataFrame, database_name: str, redshift_username: str, redshift_password: str, redshift_iam_role: str, schema_name: str, target_table: str, connection_url: str, target_s3_path: str):

    try:
        current_date = datetime.now().strftime('%Y-%m-%d')
        temp_dir = os.path.join(target_s3_path, "tmp",f"date={current_date}")
        table = f"{schema_name}.{target_table}"

        connection_url = os.path.join(connection_url, f"{database_name}?user={redshift_username}&password={redshift_password}")

        df.write \
            .format("io.github.spark_redshift_community.spark.redshift") \
            .option("url", connection_url) \
            .option("dbtable", table) \
            .option("tempdir", temp_dir) \
            .option("aws_iam_role", redshift_iam_role) \
            .option("tempformat", "PARQUET") \
            .mode("append") \
            .save()

        # .mode ->
        # "error" will cause the operation to fail if data already exists in the target location.
        # "overwrite" might be more suitable if we intend to replace existing data.
        # "append" could be used if we are adding to an existing dataset.

        logger.info("Data loaded to Redshift table successfully.")

    except Exception as e:
        logger.error(f"An error occurred in load_to_redshift_with_connector(): {str(e)}")
        raise


def get_secret(secret_name, region_name):
    """Retrieve and parse secret from AWS Secrets Manager."""
    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager', region_name=region_name)
    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        if 'SecretString' in get_secret_value_response:
            secret = get_secret_value_response['SecretString']
            return json.loads(secret)
        else:
            return None
    except Exception as e:
        logger.error(f"Error retrieving secret: {str(e)}")
        raise e




def init_spark_session(aws_credentials):
    """Initialize Spark session with AWS credentials for S3 access."""
    spark = SparkSession.builder \
        .appName("GlueApp") \
        .config("spark.hadoop.fs.s3a.access.key", aws_credentials['access_key']) \
        .config("spark.hadoop.fs.s3a.secret.key", aws_credentials['secret_key']) \
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .getOrCreate()
    return spark


# def init_spark_session(aws_credentials):
#     """Initialize Spark session with AWS credentials for S3 access and print versions."""
#     spark = SparkSession.builder \
#         .appName("GlueApp") \
#         .config("spark.hadoop.fs.s3a.access.key", aws_credentials['access_key']) \
#         .config("spark.hadoop.fs.s3a.secret.key", aws_credentials['secret_key']) \
#         .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
#         .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
#         .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
#         .config("spark.delta.logStore.class", "org.apache.spark.sql.delta.storage.S3SingleDriverLogStore") \
#         .getOrCreate()
#
#     print("Apache Spark version:", spark.version)
#     print("Configured Delta Lake.")
#     return spark



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
            "TARGET_BUCKET_NAME",
            "REDSHIFT_SECRET_NAME",
            "STAGE",
            "REGION",
            "REDSHIFT_WORKGROUP_NAME",
            "DATABASE_NAME",
            "CONNECTION_NAME",
            "REDSHIFT_USER_NAME",
            "REDSHIFT_PASS"
        ],
    )

    gc, job, logger = init_job(args)


    target_bucket_name = args["TARGET_BUCKET_NAME"]
    stage = args["STAGE"]
    secret_name = args["REDSHIFT_SECRET_NAME"]
    aws_region = args["REGION"]
    workgroup_name = args["REDSHIFT_WORKGROUP_NAME"]
    database_name = "dev" #args["DATABASE_NAME"]
    redshift_schema_name = "glue_ingest" #args["DATABASE_NAME"]
    redshift_table_name = 'ad_search_events'
    connection_name = args["CONNECTION_NAME"]
    redshift_username = args["REDSHIFT_USER_NAME"]
    redshift_password = args["REDSHIFT_PASS"]
    redshift_iam_role = "arn:aws:iam::730335331410:role/data-platform-rs-pro-redshift-serverless-role"


    secret_name = "glue-read-from-datahub-credential"
    credentials = get_secret(secret_name, aws_region)


    # build a spark session
    #ss: SparkSession = gc.spark_session

    ss = init_spark_session(credentials)


    #s3_bucket = "dl-mobilede-ds-platform-pro-datalake-xgukef6on6j2/mo-delta-tables/ad_search_events_table/svc-ad-search/"
    #delta_table_path = "s3://dl-mobilede-ds-platform-pro-datalake-xgukef6on6j2/mo-delta-tables/ad_search_events_table/svc-ad-search"

    s3_bucket = "dl-mobilede-ds-platform-pro-datalake-xgukef6on6j2/mo-delta-ad-search-events/svc-ad-search"
    delta_table_path = "s3://dl-mobilede-ds-platform-pro-datalake-xgukef6on6j2/mo-delta-ad-search-events/svc-ad-search"


    # target_s3_path= "s3://mo-dev-glue-data-bucket/pro/ad_search_events_table"
    # reconstruct_delta_table(ss, delta_table_path, target_s3_path)

    session = boto3.Session(
        aws_access_key_id=credentials['access_key'],
        aws_secret_access_key=credentials['secret_key'],
        region_name=aws_region
    )
    s3 = session.client('s3')
    response = s3.list_objects_v2(Bucket=s3_bucket.split('/')[0], Prefix='/'.join(s3_bucket.split('/')[1:]))

    if 'Contents' in response:
        for item in response['Contents']:
            print(item['Key'])
    else:
        print("No items found in the specified path.")

        # Apache Spark version: 3.3.0-amzn-1


    #path = "s3://mo-dev-glue-data-bucket/new_delta_table"
    #ss.sparkContext.setLogLevel("DEBUG")
    #ss.catalog.clearCache()


    #ss.sql(f"REFRESH TABLE delta.`{delta_table_path}`")


    deltaTable = DeltaTable.forPath(ss, delta_table_path)
    deltaTable.toDF().show()
    # df = ss.read.format("delta").load(delta_table_path)
    # df.show()


    # df = spark_read_delta_df(ss, delta_table_path)
    # df.show()


    # s3 = boto3.resource("s3")
    # client = boto3.client("s3")
    # bucket = s3.Bucket(target_bucket_name)
    #
    # session = boto3.session.Session()
    # sm_client = session.client(service_name='secretsmanager', region_name=aws_region)
    # secret_arn = get_secret_arn(secret_name, sm_client)
    #
    # query = " select * from dev.test_schema.users "
    # table_name = 'external_table'
    # connection_url = "jdbc:redshift://data-platform-rs-wg.730335331410.eu-central-1.redshift-serverless.amazonaws.com:5439"
    # target_s3_path = f"s3://{target_bucket_name}"
    #
    # glue_catalog_database_name = "glue_database"
    # glue_catalog_table_name = "glue_mo_delta_ad_search_events_730335331410_eu_central_1"
    # #catalog_df = df_from_catalog(glue_catalog_database_name, glue_catalog_table_name, gc)
    #
    # #delta_table_path ="s3://mo-delta-ad-search-events-730335331410-eu-central-1/"
    # delta_table_path ="s3://mo-dev-glue-data-bucket/new_delta_table/"
    #
    # #reconstruct_delta_table(ss, delta_table_path, target_s3_path)
    #
    #
    # df = spark_read_delta_df(ss, delta_table_path)
    # df.show(n=5)

    # role = "arn:aws:iam::360928389411:role/Mo-Data-Redshift-MVP"
    #
    #
    # load_to_redshift_with_connector(
    #     df,
    #     database_name,
    #     redshift_username,
    #     redshift_password,
    #     redshift_iam_role,
    #     redshift_schema_name,
    #     redshift_table_name,
    #     connection_url,
    #     target_s3_path)


    #fetch_schema_df = fetch_schema(ss, glue_catalog_database_name, glue_catalog_table_name)
    ## create external table
    external_schema_name = "external_schema"
    # external_schema_sql = f"""
    # CREATE EXTERNAL SCHEMA {external_schema_name} FROM DATA CATALOG
    #   DATABASE '{glue_catalog_database_name}'
    #   IAM_ROLE '{spectrum_iam_role}'
    #   REGION 'eu-central-1';
    # """
    # create_external_table = execute_rs_query(external_schema_sql, database_name, workgroup_name, secret_arn)

    # fetch_schema_df = fetch_schema_external(database_name, external_schema_name, glue_catalog_table_name, workgroup_name, secret_arn, ss)
    # #fetch_schema_df.show(n=fetch_schema_df.count(), truncate=False)
    #
    #
    # if fetch_schema_df is not None and catalog_df is not None:
    #     # max_length_df = calc_max_length_df(ss, catalog_df, fetch_schema_df)
    #     # query = create_table_query(ss, catalog_df, fetch_schema_df, max_length_df, redshift_schema_name, redshift_table_name)
    #     # print("++++++++++++query++++++++++++")
    #     # print(query)
    #     # create_table = execute_rs_query(query, database_name, workgroup_name, secret_arn)
    #
    #
    #     ## select all from external table and insert in the new created redshift table
    #     insert_to_redshift_query = f"""
    #     INSERT INTO {database_name}.{redshift_schema_name}.{redshift_table_name}
    #     SELECT * FROM {database_name}.{external_schema_name}.{glue_catalog_table_name};
    #     """
    #     insert_to_redshift = execute_rs_query(insert_to_redshift_query, database_name, workgroup_name, secret_arn)

    job.commit()