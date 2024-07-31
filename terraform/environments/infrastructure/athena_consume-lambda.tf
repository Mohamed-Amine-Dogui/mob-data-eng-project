########################################################################################################################
###  Redshift athena_consume lambda
########################################################################################################################
module "athena_consume_lambda" {

  source = "git::ssh://git@github.mpi-internal.com/datastrategy-mobile-de/terraform-aws-lambda-vpc-deployment.git?ref=tags/0.0.1"

  enable = true
  depends_on = [
    module.rs_mgmt_kms_key,
  ]
  stage          = var.stage
  project        = var.project
  region         = var.aws_region
  git_repository = var.git_repository


  additional_policy        = data.aws_iam_policy_document.athena_consume_lambda_policy.json
  attach_additional_policy = true

  lambda_unique_function_name = var.athena_consume_lambda_unique_function_name
  artifact_bucket_name        = module.lambda_scripts_bucket.s3_bucket
  runtime                     = "python3.9"
  handler                     = var.default_lambda_handler
  main_lambda_file            = "main"
  lambda_base_dir             = "${abspath(path.cwd)}/../../../lambdas/athena_consume"
  lambda_source_dir           = "${abspath(path.cwd)}/../../../lambdas/athena_consume/src"
  memory_size                 = 512
  timeout                     = 900
  logs_kms_key_arn            = module.rs_mgmt_kms_key.kms_key_arn

  lambda_env_vars = {
    stage              = var.stage
    REGION             = var.aws_region
    DATABASE_NAME      = "glue_database"
    TARGET_BUCKET_NAME = module.glue_data_bucket.s3_bucket
  }

  tags_lambda = {
    GitRepository = var.git_repository
    ProjectID     = "mo"
  }
}

########################################################################################################################
### Policy of athena_consume lambda
########################################################################################################################
data "aws_iam_policy_document" "athena_consume_lambda_policy" {
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
      "${module.lambda_scripts_bucket.s3_arn}",
      "${module.lambda_scripts_bucket.s3_arn}/*",
      "${module.glue_data_bucket.s3_arn}",
      "${module.glue_data_bucket.s3_arn}/*",
      "arn:aws:s3:::mo-delta-ad-search-events-730335331410-eu-central-1",
      "arn:aws:s3:::mo-delta-ad-search-events-730335331410-eu-central-1/*"
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
      "${module.rs_mgmt_kms_key.kms_key_arn}",
      "${module.lambda_scripts_bucket.aws_kms_key_arn}"
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
    sid    = "AllowAthenaExecutionAndGlueAccess"
    effect = "Allow"
    actions = [
      "athena:StartQueryExecution",
      "athena:StopQueryExecution",
      "athena:GetQueryExecution",
      "athena:GetQueryResults",
      "athena:GetWorkGroup",
      "glue:GetDatabase",
      "glue:GetDatabases",
      "glue:GetTable",
      "glue:GetTables",
      "glue:GetPartitions",
    ]
    resources = [
      "arn:aws:athena:${var.aws_region}:${local.account_id}:workgroup/primary",
      "arn:aws:glue:${var.aws_region}:${local.account_id}:catalog",
      "arn:aws:glue:${var.aws_region}:${local.account_id}:database/mo_dev_delta_db",
      "arn:aws:glue:${var.aws_region}:${local.account_id}:table/mo_dev_delta_db/delta_ad_search",
    ]
  }
  statement {
    sid    = "LakeFormation"
    effect = "Allow"
    actions = [
      "lakeformation:GetDataAccess"
    ]
    resources = ["*"]
  }
}


########################################################################################################################
###   Allows to grant permissions to lambda to use the specified KMS key
########################################################################################################################
resource "aws_kms_grant" "athena_consume_lambda_grant_kms_key" {
  count             = local.count_in_default
  name              = module.generic_labels.resource["grant"]["id"]
  key_id            = module.rs_mgmt_kms_key.kms_key_id
  grantee_principal = module.athena_consume_lambda.aws_lambda_function_role_arn
  operations = [
    "Decrypt",
    "Encrypt",
    "GenerateDataKey",
    "DescribeKey"
  ]
}





