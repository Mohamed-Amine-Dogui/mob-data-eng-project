
## DDR Process Documentation for GDPR Compliance

### Overview

Our system ensures GDPR compliance by anonymizing and managing user data stored in AWS Redshift. This is achieved through daily automated processes which handle anonymized data insertion and selective data deletion based on predefined criteria. This document describes the architecture and workflow of the Data Deletion and Replacement (DDR) processes.

### System Architecture

#### Data Storage and Management

- AWS Redshift: Serves as data warehouse where user data is stored.
- AWS S3: Hosts two types of files for each Redshift table:
    1. Avro files (.avro): Contain anonymized records ready to be inserted into Redshift.
    2. SQL files (.sql): Contain SQL commands to delete specific records from Redshift tables.

#### Automation and Processing

- AWS Step Functions: Orchestrates daily automated tasks using cron job triggers.
- AWS Lambda: Executes data handling scripts:
    1. ddr_delete_lambda: Manages deletion of records.
    2. ddr_copy_lambda: Handles insertion of anonymized data.

### Workflow Description

#### Daily Processes

1. Data Generation:
    - Two separate jobs generate necessary files daily and store them in specific S3 paths linked to Redshift table names and dates:
        - Avro File Generation: Anonymizes existing records and outputs `.avro` files.
        - SQL File Generation: Outputs `.sql` files containing deletion commands.

2. Step Function Triggers:
    - Triggered daily to initiate the DDR processes for data handling from the previous day's data generation.

3. Lambda Functions Execution:
    - ddr_delete_lambda:
        - Checks for the existence of `.sql` file (e.g., `..../2024-04-06.sql`).
        - Executes the SQL queries contained within the file to delete data from the Redshift table as specified.
    - ddr_copy_lambda:
        - Checks for the existence of `.avro` file in the corresponding date prefix (e.g., `..../date=2024-04-06/file.avro`).
        - Runs the Redshift COPY command to append anonymized data from the `.avro` file to the table.

### File Path and Naming Convention

- Files are stored in S3 with paths indicating the associated Redshift table name and the date of data generation. This standardization assists in automating data handling by matching files to their respective tables and processing dates.


----



CREATE OR REPLACE VIEW secure_view AS
SELECT head__id, head__app, head__ns, ci__name
FROM "glue_database"."glue_mo_delta_ad_search_events_730335331410_eu_central_1";



create a policy: athena_view_access :



{
"Version": "2012-10-17",
"Statement": [
{
"Sid": "AllowReadS3",
"Effect": "Allow",
"Action": [
"s3:GetObject",
"s3:ListBucket",
"s3:PutObject"
],
"Resource": [
"arn:aws:s3:::mo-delta-ad-search-events-730335331410-eu-central-1",
"arn:aws:s3:::mo-delta-ad-search-events-730335331410-eu-central-1/*"
]
},
{
"Sid": "AllowAthenaExecutionAndGlueAccessToView",
"Effect": "Allow",
"Action": [
"glue:GetTable",
"glue:GetTables",
"glue:GetDatabase",
"glue:GetDatabases",
"glue:GetPartitions",
"athena:StartQueryExecution",
"athena:StopQueryExecution",
"athena:GetQueryExecution",
"athena:GetQueryResults",
"athena:GetWorkGroup"
],
"Resource": [
"arn:aws:glue:eu-central-1:730335331410:catalog",
"arn:aws:glue:eu-central-1:730335331410:database/glue_database",
"arn:aws:glue:eu-central-1:730335331410:table/glue_database/secure_view",
"arn:aws:glue:eu-central-1:730335331410:table/glue_database/glue_mo_delta_ad_search_events_730335331410_eu_central_1",
"arn:aws:athena:eu-central-1:730335331410:workgroup/primary"
]
},
{
"Sid": "DenyAccessToOtherTables",
"Effect": "Deny",
"Action": [
"glue:GetTable",
"glue:GetTables"
],
"Resource": [
"arn:aws:glue:eu-central-1:730335331410:table/glue_database/*"
],
"Condition": {
"StringNotLike": {
"aws:ResourceArn": [
"arn:aws:glue:eu-central-1:730335331410:table/glue_database/secure_view",
"arn:aws:glue:eu-central-1:730335331410:table/glue_database/glue_mo_delta_ad_search_events_730335331410_eu_central_1"
]
}
}
}
]
}



1 one cron job on a VM running dbt Model
several python scripts also in the same VM and same cron job

2 a day
on BigQuery
data sources : huge bigQuery table ->
mo-data-lake-prod-k4pi.ga_events.ga_hits_mobile_silver
mo-data-lake-prod-k4pi.ga_events.ga_sessions_mobile_silver

-> looker 



## Documentation for Managing Column-Level Access in AWS Glue and Athena

### Purpose

The purpose of this document is to describe the approach to achieve Personally Identifiable Information (PII) protection by managing column-level access for different consumers (e.g., humans, Lambda functions, Unicorn) in an AWS Glue and Athena environment. Specifically, we aim to ensure that:
- Consumer A can access columns A and B.
- Consumer B cannot access columns A, B, C, and D.
- Consumer C cannot access columns A, B, C, D, and E.

### Approach

To manage column-level access, we considered two primary approaches:
1. Using AWS Glue Views and IAM Policies
2. Using AWS Lake Formation

### Approach 1: AWS Glue Views and IAM Policies

#### Step 1: Creating Views

1. **Run a Glue Crawler**: First, run a Glue crawler on the Delta table to create a catalog entry in the Glue Data Catalog.
2. **Create Views**: Create different views on top of the Delta table, selecting only the necessary columns for each consumer. For example:
    - `secure_view_A`: Selects only columns A and B.
    - `secure_view_B`: Excludes columns A, B, C, and D.
    - `secure_view_C`: Excludes columns A, B, C, D, and E.

#### Step 2: IAM Policies

Attach an IAM role with a policy to each consumer. The policy should allow access only to the specific views while denying access to other columns. Example IAM policy for a consumer:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowReadS3",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket",
        "s3:PutObject"
      ],
      "Resource": [
        "arn:aws:s3:::mo-delta-ad-search-events-730335331410-eu-central-1",
        "arn:aws:s3:::mo-delta-ad-search-events-730335331410-eu-central-1/*"
      ]
    },
    {
      "Sid": "AllowAthenaExecutionAndGlueAccessToView",
      "Effect": "Allow",
      "Action": [
        "glue:GetTable",
        "glue:GetTables",
        "glue:GetDatabase",
        "glue:GetDatabases",
        "glue:GetPartitions",
        "athena:StartQueryExecution",
        "athena:StopQueryExecution",
        "athena:GetQueryExecution",
        "athena:GetQueryResults",
        "athena:GetWorkGroup"
      ],
      "Resource": [
        "arn:aws:glue:eu-central-1:730335331410:catalog",
        "arn:aws:glue:eu-central-1:730335331410:database/glue_database",
        "arn:aws:glue:eu-central-1:730335331410:table/glue_database/secure_view",
        "arn:aws:athena:eu-central-1:730335331410:workgroup/primary"
      ]
    },
    {
      "Sid": "DenyAccessToOtherTables",
      "Effect": "Deny",
      "Action": [
        "glue:GetTable",
        "glue:GetTables"
      ],
      "Resource": [
        "arn:aws:glue:eu-central-1:730335331410:table/glue_database/*"
      ],
      "Condition": {
        "StringNotLike": {
          "aws:ResourceArn": [
            "arn:aws:glue:eu-central-1:730335331410:table/glue_database/secure_view"
          ]
        }
      }
    }
  ]
}
```

#### Step 3: Testing with Lambda Function

To test the setup, create a Lambda function that uses API calls to create a CSV file based on a query selecting data from the view. Note that the Lambda function also requires permissions to access the underlying table, leading to a modified IAM policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowReadS3",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket",
        "s3:PutObject"
      ],
      "Resource": [
        "arn:aws:s3:::mo-delta-ad-search-events-730335331410-eu-central-1",
        "arn:aws:s3:::mo-delta-ad-search-events-730335331410-eu-central-1/*"
      ]
    },
    {
      "Sid": "AllowAthenaExecutionAndGlueAccessToView",
      "Effect": "Allow",
      "Action": [
        "glue:GetTable",
        "glue:GetTables",
        "glue:GetDatabase",
        "glue:GetDatabases",
        "glue:GetPartitions",
        "athena:StartQueryExecution",
        "athena:StopQueryExecution",
        "athena:GetQueryExecution",
        "athena:GetQueryResults",
        "athena:GetWorkGroup"
      ],
      "Resource": [
        "arn:aws:glue:eu-central-1:730335331410:catalog",
        "arn:aws:glue:eu-central-1:730335331410:database/glue_database",
        "arn:aws:glue:eu-central-1:730335331410:table/glue_database/secure_view",
        "arn:aws:glue:eu-central-1:730335331410:table/glue_database/glue_mo_delta_ad_search_events_730335331410_eu_central_1",
        "arn:aws:athena:eu-central-1:730335331410:workgroup/primary"
      ]
    },
    {
      "Sid": "DenyAccessToOtherTables",
      "Effect": "Deny",
      "Action": [
        "glue:GetTable",
        "glue:GetTables"
      ],
      "Resource": [
        "arn:aws:glue:eu-central-1:730335331410:table/glue_database/*"
      ],
      "Condition": {
        "StringNotLike": {
          "aws:ResourceArn": [
            "arn:aws:glue:eu-central-1:730335331410:table/glue_database/secure_view",
            "arn:aws:glue:eu-central-1:730335331410:table/glue_database/glue_mo_delta_ad_search_events_730335331410_eu_central_1"
          ]
        }
      }
    }
  ]
}
```

This approach is not 100% secure because consumers could potentially access all columns and exclude the needed ones.

### Approach 2: AWS Lake Formation

#### Step 1: Configure Lake Formation

1. **Register the Delta Table**: Register the Delta table in AWS Lake Formation.
2. **Create Column-Level Permissions**: Create column-level permissions by defining different filters on top of the table for each consumer. For example:
    - Filter for Consumer A: Allows access to columns A and B.
    - Filter for Consumer B: Denies access to columns A, B, C, and D.
    - Filter for Consumer C: Denies access to columns A, B, C, D, and E.

#### Step 2: Grant Permissions

Grant access to each IAM role for the filtered tables, ensuring that each role sees only the authorized columns. The IAM roles for consumers will look similar to this:


