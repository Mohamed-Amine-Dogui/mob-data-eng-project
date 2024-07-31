
### 1. **Set Up the AWS Glue Data Catalog**

- **Catalog the Data**: Using AWS Glue to catalog the data in S3 sets the foundation for data management and querying. This process involves creating and running a Glue crawler that identifies your data structure and registers it in the Glue Data Catalog.

- **Crawl the Data**: The crawler inspects the S3 bucket, recognizing data formats and schemas, and then populates the Glue Data Catalog with corresponding table definitions.


### 2. **Use Redshift Spectrum to Query Your S3 Data**

- **Set Up Redshift Spectrum**: Ensure your Redshift is configured to use Redshift Spectrum. This step includes creating an IAM role with the necessary permissions for Spectrum to access your S3 data.

- **Create External Schema and Tables**: Link your Redshift environment with the AWS Glue Data Catalog.

  ```sql
  CREATE EXTERNAL SCHEMA myexternal_schema FROM DATA CATALOG
  DATABASE 'glue_database'
  IAM_ROLE 'arn:aws:iam::730335331410:role/data-platform-rs-pro-redshift-serverless-role'
  REGION 'eu-central-1';
  ```


### 3. **Leverage AWS Lambda for Schema Management**

1-Fetch the schema from the Redshift Spectrum external table.
  ```sql
  SELECT columnname, external_type
  FROM SVV_EXTERNAL_COLUMNS
  WHERE schemaname = 'external_schema'
  AND tablename = 'glue_mo_delta_ad_search_events_730335331410_eu_central_1';
  ```
2-Map the column data types to Redshift-compatible types.
3-Create a table in Redshift using the mapped schema.

### 4. **Insert Value from external table into internal Table **

  ```sql
    INSERT INTO dev.internal_schema.test
    SELECT * FROM dev.external_schema.glue_mo_delta_ad_search_events_730335331410_eu_central_1;
  ```

### 4. **This works**

  ```sql
    COPY dev.glue_ingest.ad_search_events
    FROM 's3://mo-dev-glue-data-bucket/new_delta_table/date=2024-04-18/'
    IAM_ROLE 'arn:aws:iam::730335331410:role/data-platform-rs-pro-redshift-serverless-role'
    FORMAT AS PARQUET SERIALIZETOJSON
    REGION 'eu-central-1';
  ```

### 5. **Debugguing Redshift **

  ```sql
    select * from pg_user;

    -- Query ID: 16049342
    -- pid=1073979722
        
    SELECT *
    FROM SYS_LOAD_ERROR_DETAIL
    ORDER BY start_time DESC;

    
    SYS_LOAD_HISTORY and SYS_LOAD_ERROR_DETAIL
    
    
    SELECT *
    FROM SYS_LOAD_ERROR_DETAIL
    WHERE query_id = 16049342
  ```


### 5. **Establish fine-granular access control (column-level) **

  ```sql
    select * from pg_user;

    -- Query ID: 16049342
    -- pid=1073979722
        
    SELECT *
    FROM SYS_LOAD_ERROR_DETAIL
    ORDER BY start_time DESC;

    
    SYS_LOAD_HISTORY and SYS_LOAD_ERROR_DETAIL
    
    
    SELECT *
    FROM SYS_LOAD_ERROR_DETAIL
    WHERE query_id = 16049342
  ```




Wenn ein AWS Glue-Job mit dem Delta Lake-Paket konfiguriert ist, ermöglicht er das Lesen von Daten aus einer Delta Lake-Tabelle unter Berücksichtigung der Transaktionsprotokolle, die im Verzeichnis _delta_log gespeichert sind. Das resultierende DataFrame spiegelt somit die neueste Version der Tabelle wider, einschließlich aller Updates, Löschungen und Einfügungen.

Zur Aktualisierung einer Redshift-Tabelle:

1. Daten aus der Delta Lake-Tabelle werden in ein DataFrame gelesen.
2. Das DataFrame wird als Parquet-Datei an einen temporären S3-Speicherort geschrieben.
3. Mit dem Redshift-COPY-Befehl werden die Daten von S3 in eine Staging-Tabelle in Redshift geladen.
4. Durch SQL-MERGE- oder UPSERT-Befehle wird die Haupttabelle in Redshift mit den Änderungen aus der Staging-Tabelle aktualisiert.
5. Die Daten in der Staging-Tabelle sowie die temporären Daten in S3 werden gelöscht


https://github.com/spark-redshift-community/spark-redshift

### 5. Create a Lambda Layer **

  ```bash
  #!/usr/bin/env bash
  
  set -e -x
  
  # Define variables
  LAYER_NAME="psycopg2-layer"
  PYTHON_VERSION="python3.9"
  REGION="eu-central-1"
  LAYER_DIR="psycopg2-layer"
  PACKAGE="aws-psycopg2==1.3.8"
  
  # Set AWS profile
  export AWS_PROFILE="data_redshift"
  
  # PATH
  LAMBDA_NAME=$(basename "${PWD}")
  LAMBDAS_DIR=$(dirname "${PWD}")
  
  echo "Building ${LAMBDA_NAME} Lambda..."
  
  # Load common functions
  source "${LAMBDAS_DIR}/common_bash/build.sh"
  
  # Install dependencies for the Lambda function
  installDependenciesLambda "${LAMBDA_NAME}" "${LAMBDAS_DIR}" true "3.9"
  
  # Create directory for the layer
  mkdir -p "${LAYER_DIR}/python/lib/python${PYTHON_VERSION}/site-packages"
  
  # Install package into the layer directory
  pip install $PACKAGE -t "${LAYER_DIR}/python/lib/python${PYTHON_VERSION}/site-packages"
  
  # Zip the directory
  cd "$LAYER_DIR"
  zip -r "${LAYER_NAME}.zip" python
  
  # Upload the layer to AWS Lambda
  aws lambda publish-layer-version --layer-name "$LAYER_NAME" --zip-file "fileb://${LAYER_NAME}.zip" --compatible-runtimes "python3.9"
  ```






