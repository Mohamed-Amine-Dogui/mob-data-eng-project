########################################################################################################################
###  Redshift management lambda
########################################################################################################################
module "redshift_management_lambda" {

  source = "git::ssh://git@github.mpi-internal.com/datastrategy-mobile-de/terraform-aws-lambda-vpc-deployment.git?ref=tags/0.0.1"

  enable = true
  depends_on = [
    module.rs_mgmt_kms_key,
  ]
  stage          = var.stage
  project        = var.project
  region         = var.aws_region
  git_repository = var.git_repository


  additional_policy        = data.aws_iam_policy_document.schema_lambda_policy.json
  attach_additional_policy = true

  lambda_unique_function_name = var.redshift_schema_lambda_unique_function_name
  artifact_bucket_name        = module.lambda_scripts_bucket.s3_bucket
  runtime                     = "python3.9"
  handler                     = var.default_lambda_handler
  main_lambda_file            = "main"
  lambda_base_dir             = "${abspath(path.cwd)}/../../../lambdas/redshift_management"
  lambda_source_dir           = "${abspath(path.cwd)}/../../../lambdas/redshift_management/src"
  memory_size                 = 512
  timeout                     = 900
  logs_kms_key_arn            = module.rs_mgmt_kms_key.kms_key_arn

  lambda_env_vars = {
    stage                    = var.stage
    REGION                   = var.aws_region
    DATABASE_NAME            = "dev"
    REDSHIFT_SECRET_NAME     = "data_platform_rs_db"
    REDSHIFT_WORKGROUP_NAME  = "data-platform-rs-wg"
    GLUE_CATALOG_SCHEMA_NAME = ""
    REDSHIFT_SCHEMA_NAME     = ""

  }

  tags_lambda = {
    GitRepository = var.git_repository
    ProjectID     = "mo"
  }
}

########################################################################################################################
### Policy of schema lambda
########################################################################################################################
data "aws_iam_policy_document" "schema_lambda_policy" {
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
resource "aws_kms_grant" "schema_lambda_grant_kms_key" {
  count             = local.count_in_default
  name              = module.generic_labels.resource["grant"]["id"]
  key_id            = module.rs_mgmt_kms_key.kms_key_id
  grantee_principal = module.redshift_management_lambda.aws_lambda_function_role_arn
  operations = [
    "Decrypt",
    "Encrypt",
    "GenerateDataKey",
    "DescribeKey"
  ]
}

########################################################################################################################
###   Upload the sql file to s3
########################################################################################################################
resource "aws_s3_object" "redshift_schema_table_user" {
  depends_on     = [module.redshift_management_lambda]
  bucket         = module.redshift_schema_bucket.s3_bucket
  key            = "users.sql"
  content_base64 = filebase64("${path.module}/../../../lambdas/redshift_management/schemas/users.sql")
}

########################################################################################################################
###   Allow Bucket to send Notification to AWS Lambda
########################################################################################################################

resource "aws_lambda_permission" "allow_bucket" {
  statement_id  = "AllowExecutionFromS3Bucket"
  action        = "lambda:InvokeFunction"
  function_name = module.redshift_management_lambda.aws_lambda_function_arn
  principal     = "s3.amazonaws.com"
  source_arn    = module.redshift_schema_bucket.s3_arn
}

resource "aws_s3_bucket_notification" "bucket_notification" {
  bucket = module.redshift_schema_bucket.s3_id

  lambda_function {
    lambda_function_arn = module.redshift_management_lambda.aws_lambda_function_arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = ""
    filter_suffix       = ".sql"
  }
  depends_on = [aws_lambda_permission.allow_bucket]
}