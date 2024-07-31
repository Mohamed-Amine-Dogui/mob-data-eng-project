import logging
from logging import Logger
import os
import sys
from datetime import datetime, timedelta
from typing import Tuple

import boto3
from awsglue import DynamicFrame
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import SparkSession, DataFrame
#from pyspark.sql import functions as f
#from pyspark.sql.functions import current_date
#from pyspark.sql.types import StructType, StructField, StringType, IntegerType
import time

#import pandas as pd
from botocore.exceptions import ClientError

sys.path.insert(0, "/tmp/")

logger: Logger = logging.getLogger()

# Version of the glue job
__version__ = "0.4.0"

def get_secret_arn(secret_name, sm_client):
    try:
        response = sm_client.describe_secret(SecretId=secret_name)
        return response['ARN']
    except ClientError as e:
        logger.error(f"Error retrieving secret ARN: {str(e)}")
        raise e

# def wait_for_query_completion(redshift_data_client, query_id):
#     while True:
#         response = redshift_data_client.describe_statement(Id=query_id)
#         status = response['Status']
#         if status in ['FINISHED', 'FAILED', 'ABORTED']:
#             return status
#         time.sleep(10)

def read_from_redshift_pyspark(
        connection_url,
        query,
        redshift_username,
        redshift_password,
        target_s3_path,
        table_name,
        gc
):
    try:
        copy_cmd_tmp_dir = os.path.join(target_s3_path, "tmp", table_name)
        connection_options = {
            "url": connection_url,
            "query": query,
            "user": redshift_username,
            "password": redshift_password,
            "redshiftTmpDir": copy_cmd_tmp_dir,
        }

        logger.info(f"Connecting to Redshift with options: {connection_options}")

        # Attempt to create a dynamic frame from the Redshift connection options
        df = gc.create_dynamic_frame_from_options("redshift", connection_options).toDF()

        if df:
            logger.info(f"Connection to Redshift established successfully.")
        else:
            logger.warning(f"Connection to Redshift was successful, but no data was returned.")

        return df
    except Exception as e:
        logger.error(f"Error connecting to Redshift: {e}")
        raise ConnectionError("Failed to connect to Redshift.") from e


# def read_from_redshift_pandas(schemaname, tablename, database_name, workgroup_name, secret_arn):
#     redshift_data_client = boto3.client('redshift-data')
#     fetch_query = f"""
#     SELECT * FROM "dev"."external_schema"."glue_mo_delta_ad_search_events_730335331410_eu_central_1";
#     """
#     try:
#
#         response = redshift_data_client.execute_statement(
#             Database=database_name,
#             Sql=fetch_query,
#             WorkgroupName=workgroup_name,
#             SecretArn=secret_arn
#         )
#         query_id = response['Id']
#         status = wait_for_query_completion(redshift_data_client, query_id)
#         if status == 'FINISHED':
#             result = redshift_data_client.get_statement_result(Id=query_id)
#             # need to writhe the code to transform the result into a pandas df
#             return df
#         else:
#             raise Exception(f"Query {query_id} did not finish successfully.")
#     except Exception as e:
#         logger.error(f"Error executing SQL script through Redshift Data API: {str(e)}")
#         raise

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
            "REGION"
        ],
    )

    gc, job, logger = init_job(args)
    # build a spark session
    ss: SparkSession = gc.spark_session

    target_bucket_name = args["TARGET_BUCKET_NAME"]
    stage = args["STAGE"]
    secret_name = args["REDSHIFT_SECRET_NAME"]
    region_name = args["REGION"]

    s3 = boto3.resource("s3")
    client = boto3.client("s3")
    bucket = s3.Bucket(target_bucket_name)

    session = boto3.session.Session()
    sm_client = session.client(service_name='secretsmanager', region_name=region_name)

    secret_arn = get_secret_arn(secret_name, sm_client)

    connection_url = "jdbc:redshift://data-platform-rs.730335331410.eu-central-1.redshift-serverless.amazonaws.com:5439/data_platform_rs_db"
    redshift_username ="dsadmin"
    redshift_password = "36o6hm2hX8s5rzwrV6vSL0fz"

    #uery = ' SELECT * FROM dev.external_schema.glue_mo_delta_ad_search_events_730335331410_eu_central_1; '

    query = " select * from dev.test_schema.users "

    table_name = 'external_table'
    target_s3_path = f"s3://{target_bucket_name}"


    df = read_from_redshift_pyspark(
        connection_url,
        query,
        redshift_username,
        redshift_password,
        target_s3_path,
        table_name,
        gc
    )

    df.show()


    job.commit()