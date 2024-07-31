########################################################################################################################
###  Import psycopg2-layer
########################################################################################################################
#data "aws_lambda_layer_version" "psycopg2-layer" {
#  layer_name = "psycopg2-layer"
#}

########################################################################################################################
###  Redshift ddr_copy lambda
########################################################################################################################
module "ddr_copy_lambda" {

  source = "git::ssh://git@github.mpi-internal.com/datastrategy-mobile-de/terraform-aws-lambda-vpc-deployment.git?ref=tags/0.0.1"

  enable = true
  depends_on = [
    module.rs_mgmt_kms_key,
  ]
  stage          = var.stage
  project        = var.project
  region         = var.aws_region
  git_repository = var.git_repository


  additional_policy        = data.aws_iam_policy_document.ddr_copy_lambda_policy.json
  attach_additional_policy = true

  lambda_unique_function_name = var.ddr_copy_lambda_unique_function_name
  artifact_bucket_name        = module.lambda_scripts_bucket.s3_bucket
  runtime                     = "python3.9"
  handler                     = var.default_lambda_handler
  main_lambda_file            = "main"
  lambda_base_dir             = "${abspath(path.cwd)}/../../../lambdas/ddr_copy"
  lambda_source_dir           = "${abspath(path.cwd)}/../../../lambdas/ddr_copy/src"
  memory_size                 = 512
  timeout                     = 900
  logs_kms_key_arn            = module.rs_mgmt_kms_key.kms_key_arn

  lambda_env_vars = {
    stage                   = var.stage
    REGION                  = var.aws_region
    DATABASE_NAME           = "data_platform_rs_db"
    REDSHIFT_SECRET_NAME    = "data_platform_rs_db"
    REDSHIFT_WORKGROUP_NAME = "data-platform-rs-wg"
    REDSHIFT_USER_NAME      = local.db_credentials.username
    REDSHIFT_PASS           = local.db_credentials.password
    TARGET_REDSHIFT_SCHEMA  = "public"
    TARGET_REDSHIFT_TABLE   = "email_contact_raw_20230617"
    REDSHIFT_ENDPOINT       = "data-platform-rs-wg.730335331410.eu-central-1.redshift-serverless.amazonaws.com"
    SOURCE_S3_AVRO_PATH     = "s3://mvp-delta-tmp-laurenz/email-contact-anonymized-avro/"
    REDSHIFT_IAM_ROLE       = "arn:aws:iam::730335331410:role/data-platform-rs-pro-redshift-serverless-role"
    GLUE_USER_SECRET_NAME   = "glue-read-from-datahub-credential"
  }

  #  lambda_layers = [
  #    data.aws_lambda_layer_version.psycopg2-layer.arn
  #  ]

  tags_lambda = {
    GitRepository = var.git_repository
    ProjectID     = "mo"
  }
}

########################################################################################################################
### Policy of ddr_copy lambda
########################################################################################################################
data "aws_iam_policy_document" "ddr_copy_lambda_policy" {
  /*
https://docs.aws.amazon.com/kms/latest/developerguide/key-policies.html
 checkov:skip=CKV_AWS_111:Skip reason - DescribeStatement requires (*) in the policy. See the link below for more information:
 checkov:skip=CKV_AWS_107:Skip reason - Credentials are not suspended.
Source: https://docs.aws.amazon.com/kms/latest/developerguide/kms-api-permissions-reference.html
*/
  statement {
    sid    = "AllowReadWriteS3"
    effect = "Allow"
    actions = [
      "s3:Get*",
      "s3:List*",
      "s3:Describe*",
      "s3:Put*",
      "s3:Delete*",
      "s3:RestoreObject"
    ]
    resources = [
      module.lambda_scripts_bucket.s3_arn,
      "${module.lambda_scripts_bucket.s3_arn}/*",
      "arn:aws:s3:::dl-mobilede-ds-platform-pro-datalake-xgukef6on6j2",
      "arn:aws:s3:::dl-mobilede-ds-platform-pro-datalake-xgukef6on6j2/*",
      module.glue_data_bucket.s3_arn,
      "${module.glue_data_bucket.s3_arn}/*",
    ]
  }

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
      module.lambda_scripts_bucket.aws_kms_key_arn
    ]
  }


  statement {

    sid    = "AllowLambdaAccessRedshift"
    effect = "Allow"
    actions = [
      "redshift-data:CancelStatement",
      "redshift:GetClusterCredentials",
      "redshift-data:DescribeStatement",
      "redshift-data:ExecuteStatement",
      "redshift-data:GetStatementResult",
      "redshift:GetClusterCredentials",
      "redshift:DescribeClusters"
    ]
    resources = [
      "*"
    ]
  }

  statement {

    sid    = "AllowPutCustomMetrics"
    effect = "Allow"
    actions = [
      "cloudwatch:PutMetricData",
      "cloudwatch:PutMetricAlarm"
    ]
    resources = [
      "*"
    ]
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

}

########################################################################################################################
###   Allows to grant permissions to lambda to use the specified KMS key
########################################################################################################################
resource "aws_kms_grant" "ddr_copy_lambda_grant_kms_key" {
  count             = local.count_in_default
  name              = module.generic_labels.resource["grant"]["id"]
  key_id            = module.rs_mgmt_kms_key.kms_key_id
  grantee_principal = module.ddr_copy_lambda.aws_lambda_function_role_arn
  operations = [
    "Decrypt",
    "Encrypt",
    "GenerateDataKey",
    "DescribeKey"
  ]
}





