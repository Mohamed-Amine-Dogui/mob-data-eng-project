import json
import boto3
import logging
import os
import psycopg2
from psycopg2 import OperationalError, InterfaceError
from datetime import datetime, timedelta

# Setup logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def execute_rs_query(query, redshift_username, redshift_password, database_name, redshift_endpoint):
    conn = None
    try:
        conn = psycopg2.connect(
            dbname=database_name,
            user=redshift_username,
            password=redshift_password,
            host=redshift_endpoint,
            port='5439'
        )
        cur = conn.cursor()
        cur.execute(query)
        # Only fetch rows if it's a SELECT query
        if query.strip().upper().startswith("SELECT"):
            rows = cur.fetchall()
            for row in rows:
                logger.info(row)
        else:
            conn.commit()
    except (Exception, OperationalError, InterfaceError) as e:
        logger.error(f"Error executing SQL script: {str(e)}")
        raise
    finally:
        if conn:
            conn.close()

def get_secret(secret_name, aws_region):
    """Retrieve and parse secret from AWS Secrets Manager."""
    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager', region_name=aws_region)
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

def check_file_exist(date, s3_path, aws_region, credentials):

    if s3_path.endswith("/"):
        s3_path = f"{s3_path}{date}/"
    else:
        s3_path = f"{s3_path}/{date}/"
    print("s3_path")
    print(s3_path)

    session = boto3.Session(
        aws_access_key_id=credentials['access_key'],
        aws_secret_access_key=credentials['secret_key'],
        region_name=aws_region
    )
    s3 = session.client('s3')
    #s3 = boto3.client('s3', region_name=aws_region)
    response = s3.list_objects_v2(Bucket=s3_path.split('/')[0], Prefix='/'.join(s3_path.split('/')[1:]))

    if 'Contents' in response:
        for item in response['Contents']:
            logger.info(f"item found: {item['Key']}")
        return s3_path
    else:
        logger.info("No items found in the specified path.")
        return False

def lambda_handler(event, context):
    # aws-psycopg2==1.3.8
    redshift_username = os.getenv("REDSHIFT_USER_NAME")
    redshift_password = os.getenv("REDSHIFT_PASS")
    database_name = os.getenv("DATABASE_NAME") #"data_platform_rs_db"
    redshift_schema_name = os.getenv("TARGET_REDSHIFT_SCHEMA") #"public"
    redshift_target_table = os.getenv("TARGET_REDSHIFT_TABLE") #"email_contact_raw_20230617"
    redshift_endpoint = os.getenv("REDSHIFT_ENDPOINT") #"data-platform-rs-wg.730335331410.eu-central-1.redshift-serverless.amazonaws.com"
    redshift_iam_role = os.getenv("REDSHIFT_IAM_ROLE") #"arn:aws:iam::730335331410:role/data-platform-rs-pro-redshift-serverless-role"
    source_s3_avro_path = "dl-mobilede-ds-platform-pro-datalake-xgukef6on6j2/redshift-poc/ddr/20240413/ad_search_events/SvcAdSearch/append-to-bq"#"mo-dev-glue-data-bucket/email-contact-anonymized-avro/" #os.getenv("SOURCE_S3_AVRO_PATH")


    secret_name = os.getenv("GLUE_USER_SECRET_NAME") #"glue-read-from-datahub-credential"
    aws_region = os.getenv("REGION")

    credentials = get_secret(secret_name, aws_region)
    yesterday_date = f"date={(datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')}"

    existing_avro_file_path = check_file_exist(yesterday_date, source_s3_avro_path, aws_region, credentials)
    print("existing_avro_file_path")
    print(existing_avro_file_path)

    if existing_avro_file_path:
        query = f"""
                COPY {database_name}.{redshift_schema_name}.{redshift_target_table}
                FROM 's3://{source_s3_avro_path}'
                iam_role '{redshift_iam_role}'
                FORMAT AS avro 'auto';
                """
        logger.info(f"Executing query: {query}")
        execute_rs_query(query, redshift_username, redshift_password, database_name, redshift_endpoint)

        return {
            "statusCode": 200,
            "body": json.dumps("Query executed successfully")
        }
