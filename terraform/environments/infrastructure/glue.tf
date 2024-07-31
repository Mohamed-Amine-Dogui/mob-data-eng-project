########################################################################################################################
### Upload main Glue Job script
########################################################################################################################
resource "aws_s3_object" "glue_script" {
  bucket         = module.glue_scripts_bucket.s3_bucket
  key            = "artifact/${module.generic_labels.resource["glue-job"]["id"]}/main.py"
  content_base64 = filebase64("${path.module}/../../../etl/glue/rs_mgmt_glue/main.py")
}

#########################################################################################################################
#### connection to redshift
#########################################################################################################################
#resource "aws_glue_connection" "redshift_conn" {
#  connection_type = "JDBC"
#  name            = module.generic_labels.resource["redshift-conn"]["id"]
#  connection_properties = {
#    JDBC_CONNECTION_URL = "jdbc:redshift://data-platform-rs-wg.730335331410.eu-central-1.redshift-serverless.amazonaws.com:5439/data_platform_rs_db"
#    PASSWORD            = "36o6hm2hX8s5rzwrV6vSL0fz"
#    USERNAME            = "dsadmin"
#  }
#
#  physical_connection_requirements {
#
#    availability_zone      = "eu-central-1a"
#    security_group_id_list = [aws_security_group.glue_security_group.id]
#    subnet_id              = "subnet-06676dce8ce9f53b7" # Ensure AWS Glue Connection Uses the Private Subnet
#  }
#
#}


########################################################################################################################
### Connection to Redshift
########################################################################################################################
resource "aws_glue_connection" "redshift_conn" {
  connection_type = "JDBC"
  name            = module.generic_labels.resource["redshift-conn"]["id"]
  connection_properties = {
    JDBC_CONNECTION_URL = "jdbc:redshift://data-platform-rs-wg.730335331410.eu-central-1.redshift-serverless.amazonaws.com:5439/data_platform_rs_db"
    USERNAME            = local.db_credentials.username
    PASSWORD            = local.db_credentials.password
  }

  physical_connection_requirements {
    availability_zone      = "eu-central-1a"
    security_group_id_list = [aws_security_group.glue_security_group.id]
    subnet_id              = "subnet-06676dce8ce9f53b7" #  AWS Glue Connection must uses the Private Subnet
  }
}




########################################################################################################################
### Test Glue job
########################################################################################################################
module "rs_mgmt_glue_job" {
  enable = true

  depends_on = [
    aws_s3_object.glue_script,
    module.rs_mgmt_kms_key
  ]

  source = "git::ssh://git@github.mpi-internal.com/datastrategy-mobile-de/terraform-aws-glue-job-deployment.git?ref=tags/0.0.1"

  stage          = var.stage
  project        = var.project
  project_id     = var.project
  git_repository = var.git_repository


  region                    = var.aws_region
  job_name                  = "rs-mgmt"
  glue_version              = "4.0"
  glue_number_of_workers    = 2
  worker_type               = "G.1X"
  connections               = [aws_glue_connection.redshift_conn.name]
  script_bucket             = module.glue_scripts_bucket.s3_bucket
  glue_job_local_path       = "${path.module}/../../../etl/glue/rs_mgmt_glue/main.py"
  extra_py_files_source_dir = "${path.module}/../../../etl/glue/rs_mgmt_glue/"
  additional_python_modules = ["boto3==1.26.6"]
  create_kms_key            = false
  kms_key_arn               = module.rs_mgmt_kms_key.kms_key_arn

  // This attribute is called like this in the module but we need to retreive the KMS-key of the Target bucket where it will write the files after processing
  target_bucket_kms_key_arn = module.glue_data_bucket.aws_kms_key_arn


  default_arguments = {
    // Glue Native
    "--job-language"                     = "python"
    "--TempDir"                          = "s3://${module.glue_scripts_bucket.s3_bucket}/glue-job-tmp/"
    "--region"                           = var.aws_region
    "--enable-metrics"                   = ""
    "--enable-continuous-cloudwatch-log" = "true"
    "--enable-glue-datacatalog"          = "" # Spark will use Glue Catalog as Hive Metastore
    "--job-bookmark-option"              = "job-bookmark-enable"
    "--datalake-formats"                 = "delta"
    "--conf"                             = "spark.sql.extensions=io.delta.sql.DeltaSparkSessionExtension --conf spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog --conf spark.delta.logStore.class=org.apache.spark.sql.delta.storage.S3SingleDriverLogStore"
    #"--disable-proxy-v2"                 = "true" # This has to be commented out otherweise the job will fail

    // User defined

    "--STAGE"                   = var.stage
    "--DATABASE_NAME"           = "data_platform_rs_db"
    "--REDSHIFT_SECRET_NAME"    = "data_platform_rs_db"
    "--REDSHIFT_WORKGROUP_NAME" = "data-platform-rs-wg"
    "--TARGET_BUCKET_NAME"      = module.glue_data_bucket.s3_bucket
    "--REGION"                  = var.aws_region
    "--CONNECTION_NAME"         = aws_glue_connection.redshift_conn.name
    "--REDSHIFT_USER_NAME"      = local.db_credentials.username
    "--REDSHIFT_PASS"           = local.db_credentials.password

  }

  timeout                  = 45
  enable_additional_policy = true
  additional_policy        = data.aws_iam_policy_document.glue_job_permissions.json
}


########################################################################################################################
###  glue job permissions
########################################################################################################################

data "aws_iam_policy_document" "glue_job_permissions" {

  statement {
    sid    = "AllowDecryptEncrypt"
    effect = "Allow"
    actions = [
      "kms:Decrypt",
      "kms:Encrypt",
      "kms:GenerateDataKey",
      "kms:ReEncrypt*",
      "kms:ListKeys",
      "kms:Describe*"
    ]
    resources = [
      module.rs_mgmt_kms_key.kms_key_arn,
      module.glue_scripts_bucket.aws_kms_key_arn,
      module.glue_data_bucket.aws_kms_key_arn,
    ]
  }

  statement {
    sid    = "AllowReadWriteToBucket"
    effect = "Allow"
    actions = [
      "s3:Get*",
      "s3:Put*",
      "s3:Describe*",
      "s3:Delete*",
      "s3:RestoreObject",
      "s3:List*"
    ]
    resources = [
      module.glue_data_bucket.s3_arn,
      "${module.glue_data_bucket.s3_arn}/*",
      "arn:aws:s3:::mo-delta-ad-view-events-730335331410-eu-central-1",
      "arn:aws:s3:::mo-delta-ad-view-events-730335331410-eu-central-1/*",
      "arn:aws:s3:::mo-delta-ad-search-events-730335331410-eu-central-1",
      "arn:aws:s3:::mo-delta-ad-search-events-730335331410-eu-central-1/*",
      "arn:aws:s3:::mo-delta-ad-log-business-ads-730335331410-eu-central-1",
      "arn:aws:s3:::mo-delta-ad-log-business-ads-730335331410-eu-central-1/*",
      "arn:aws:s3:::dl-mobilede-ds-platform-dev-datalake-1g5km8cf0r16d/mo-delta-ad-search-events",
      "arn:aws:s3:::dl-mobilede-ds-platform-dev-datalake-1g5km8cf0r16d/mo-delta-ad-search-events/*",
      "arn:aws:s3:::dl-mobilede-ds-platform-pro-datalake-xgukef6on6j2/mo-delta-ad-search-events/svc-ad-search",
      "arn:aws:s3:::dl-mobilede-ds-platform-pro-datalake-xgukef6on6j2/mo-delta-ad-search-events/svc-ad-search/*",
      module.glue_scripts_bucket.s3_arn,
      "${module.glue_scripts_bucket.s3_arn}/*",
    ]
  }


  statement {
    sid    = "AllowLogging"
    effect = "Allow"
    #checkov:skip=CKV_AWS_111:Skip reason - Resource not known before apply
    actions = [
      "logs:AssociateKmsKey",
      "logs:CreateLogGroup",
      "logs:PutLogEvents",
      "logs:DescribeLogStreams",
      "logs:DescribeLogGroups",
      "logs:CreateLogStream"
    ]
    resources = ["*"]
  }

  statement {
    effect = "Allow"
    #checkov:skip=CKV_AWS_111:Skip reason - Resource not known before apply
    actions = [
      "ec2:DescribeNetworkInterfaces",
      "ec2:CreateNetworkInterface",
      "ec2:DeleteNetworkInterface",
    ]

    resources = ["*"]
  }

  statement {
    sid    = "AllowAccessSecretsManager"
    effect = "Allow"
    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret"
    ]
    resources = [
      "arn:aws:secretsmanager:${var.aws_region}:${local.account_id}:secret:*"
    ]
  }

  statement {

    sid    = "AllowAccessRedshift"
    effect = "Allow"
    actions = [
      "redshift-data:CancelStatement",
      "redshift:GetClusterCredentials",
      "redshift-data:DescribeStatement",
      "redshift-data:ExecuteStatement",
      "redshift-data:GetStatementResult",
      "redshift:DescribeClusters",
      "redshift-serverless:ListWorkgroups",
      "redshift-serverless:ListNamespaces"
    ]
    resources = [
      "*"
    ]
  }

  statement {
    sid    = "AllowAssumeRole"
    effect = "Allow"
    actions = [
      "sts:AssumeRole"
    ]
    resources = [
      "arn:aws:iam::360928389411:role/Mo-Data-Redshift-MVP"
    ]
  }

  statement {
    sid    = "AllowGlueJobAccessDatahub"
    effect = "Allow"
    actions = [
      "glue:CreateDatabase",
      "glue:GetDatabase",
      "glue:GetDatabases",
      "glue:UpdateDatabase",
      "glue:DeleteDatabase",
      "glue:CreateTable",
      "glue:GetTable",
      "glue:GetTables",
      "glue:UpdateTable",
      "glue:DeleteTable",
      "glue:GetPartition",
      "glue:GetPartitions",
      "glue:CreatePartition",
      "glue:DeletePartition",
      "glue:BatchCreatePartition",
      "glue:BatchDeletePartition",
      "glue:BatchGetPartition"
    ]
    resources = [
      "arn:aws:glue:eu-west-1:360928389411:catalog",
      "arn:aws:glue:eu-west-1:360928389411:database/datalicious",
      "arn:aws:glue:eu-west-1:360928389411:table/datalicious/*",
    ]
  }

  statement {
    sid    = "AllowAssumeRoleForDatahubGlueJobRole"
    effect = "Allow"
    actions = [
      "sts:AssumeRole"
    ]
    resources = [
      "arn:aws:iam::360928389411:role/glue-job-role"
    ]
  }

}