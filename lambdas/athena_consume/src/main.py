import json
import boto3
import logging
import os
import time


# Setup logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def check_query_status(athena, query_execution_id):
    try:
        while True:
            response = athena.get_query_execution(QueryExecutionId=query_execution_id)
            if response['QueryExecution']['Status']['State'] in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
                logger.info(f"Query {response['QueryExecution']['Status']['State']}")
                break
            time.sleep(2)  # Sleep to reduce the number of API calls
        if response['QueryExecution']['Status']['State'] == 'SUCCEEDED':
            logger.info("Query succeeded.")
            return {
                'statusCode': 200,
                'body': json.dumps("Query execution completed successfully.")
            }
        else:
            logger.error(f"Query {response['QueryExecution']['Status']['State']}")
            return {
                'statusCode': 400,
                'body': json.dumps("Query failed or was cancelled.")
            }
    except Exception as e:
        logger.error(f"Error checking query status: {e}", exc_info=True)
        raise e


def execute_athena_query(athena, query, database_name, data_source, s3_output ):

    try:
        response = athena.start_query_execution(
            QueryString=query,
            QueryExecutionContext={
                'Database': database_name,
                'Catalog': data_source  # Specify the catalog if different from 'AwsDataCatalog'
            },
            ResultConfiguration={'OutputLocation': s3_output}
        )
        query_execution_id = response['QueryExecutionId']
        logger.info(f"QueryExecutionId: {query_execution_id}")

        # Check the query status
        return check_query_status(athena, query_execution_id)
    except Exception as e:
        logger.error(f"Failed to execute query: {str(e)}", exc_info=True)
        raise e


def lambda_handler(event, context):
    database_name = "mo_dev_delta_db" #os.getenv("DATABASE_NAME") #"glue_database"
    data_source = "AwsDataCatalog"
    table = "delta_ad_search"
    aws_region = os.getenv("REGION")
    target_bucket_name = os.getenv("TARGET_BUCKET_NAME")

    #date_file = f"{datetime.now().strftime('%Y-%m-%d')}.csv"

    query = f"SELECT * FROM \"{data_source}\".\"{database_name}\".\"{table}\" LIMIT 10;"

    s3_output = f"s3://{target_bucket_name}/athena-results/"

    # Initialize Athena client
    athena = boto3.client('athena', region_name=aws_region)

    execute_athena_query(athena, query, database_name, data_source, s3_output )
