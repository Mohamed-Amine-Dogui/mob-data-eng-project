import boto3
import json
import logging
import os
import time
from botocore.exceptions import ClientError

# Setup logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def get_secret_arn(secret_name, sm_client):
    try:
        response = sm_client.describe_secret(SecretId=secret_name)
        return response['ARN']
    except ClientError as e:
        logger.error(f"Error retrieving secret ARN: {str(e)}")
        raise e

def wait_for_query_completion(redshift_data_client, query_id):
    while True:
        response = redshift_data_client.describe_statement(Id=query_id)
        status = response['Status']
        if status in ['FINISHED', 'FAILED', 'ABORTED']:
            return status
        time.sleep(10)

def execute_rs_query(query, database_name, workgroup_name, secret_arn):
    redshift_data_client = boto3.client('redshift-data')
    try:
        print("query")
        print(query)
        response = redshift_data_client.execute_statement(
            Database=database_name,
            Sql=query,
            WorkgroupName=workgroup_name,
            SecretArn=secret_arn
        )
        logger.info(f"SQL script execution started: {response['Id']}")
        return response['Id']
    except Exception as e:
        logger.error(f"Error executing SQL script through Redshift Data API: {str(e)}")
        raise

def fetch_schema(schemaname, tablename, database_name, workgroup_name, secret_arn):
    redshift_data_client = boto3.client('redshift-data')
    fetch_query = f"""
    SELECT columnname, external_type
    FROM SVV_EXTERNAL_COLUMNS
    WHERE schemaname = '{schemaname}'
    AND tablename = '{tablename}';
    """
    try:
        print("fetch_query")
        print(fetch_query)
        response = redshift_data_client.execute_statement(
            Database=database_name,
            Sql=fetch_query,
            WorkgroupName=workgroup_name,
            SecretArn=secret_arn
        )
        query_id = response['Id']
        status = wait_for_query_completion(redshift_data_client, query_id)
        if status == 'FINISHED':
            result = redshift_data_client.get_statement_result(Id=query_id)
            schema = [{"columnname": record[0]['stringValue'], "external_type": record[1]['stringValue']} for record in result['Records']]
            print("schema")
            print(schema)

            return schema
        else:
            raise Exception(f"Query {query_id} did not finish successfully.")
    except Exception as e:
        logger.error(f"Error executing SQL script through Redshift Data API: {str(e)}")
        raise

def map_type(external_type):

    if external_type.startswith('array'):
        return 'SUPER'
    elif external_type == 'string':
        return 'VARCHAR(65535)'
    elif external_type == 'timestamp':
        return 'TIMESTAMP'
    elif external_type == 'boolean':
        return 'BOOLEAN'
    elif external_type == 'int':
        return 'INTEGER'
    elif external_type.startswith('double'):
        return 'DOUBLE PRECISION'
    else:
        return 'VARCHAR(65535)'


def lambda_handler(event, context):

    region_name = os.environ["REGION"]
    secret_name = os.environ["REDSHIFT_SECRET_NAME"]
    database_name = os.environ["DATABASE_NAME"]
    workgroup_name = os.environ["REDSHIFT_WORKGROUP_NAME"]
    #table_name = os.environ["TABLE_NAME"]
    #schema_name = os.environ["SCHEMA_NAME"]
    #glue_catalog_schema_name = os.environ["GLUE_CATALOG_SCHEMA_NAME"]
    #glue_catalog_table_name = os.environ["GLUE_CATALOG_TABLE_NAME"]
    #redshift_schema_name = os.environ["REDSHIFT_SCHEMA_NAME"]
    #redshift_table_name = os.environ["REDSHIFT_TABLE_NAME"]

    glue_catalog_schema_name = "external_schema"
    glue_catalog_table_name = "glue_mo_delta_ad_search_events_730335331410_eu_central_1"
    redshift_schema_name = "internal_schema"
    redshift_table_name = "test"


    session = boto3.session.Session()
    sm_client = session.client(service_name='secretsmanager', region_name=region_name)

    secret_arn = get_secret_arn(secret_name, sm_client)
    schema = fetch_schema(glue_catalog_schema_name, glue_catalog_table_name, database_name, workgroup_name,secret_arn)

    print("schema")
    print(schema)

    columns_sql = ', '.join([f"{col['columnname']} {map_type(col['external_type'])}" for col in schema])


    sql_create_table = f""" CREATE SCHEMA IF NOT EXISTS {redshift_schema_name};
                            CREATE TABLE IF NOT EXISTS {redshift_schema_name}.{redshift_table_name} ({columns_sql});"""

    print("sql_create_table")
    print(sql_create_table)

    create_table = execute_rs_query(sql_create_table, database_name, workgroup_name, secret_arn)
    return {
        'statusCode': 200,
        'body': json.dumps(f"Table creation initiated successfully with response: {create_table}")
    }

