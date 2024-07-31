########################################################################################################################
#### Bucket for the logs
########################################################################################################################
module "logs_bucket" {
  #checkov:skip=CKV_TF_1:Skip reason
  enable = true
  source = "git::ssh://git@github.mpi-internal.com/datastrategy-mobile-de/terraform-aws-s3-bucket-deployment//s3/s3-encrypted?ref=tags/0.0.1"

  environment                       = var.stage
  project                           = var.project
  s3_bucket_name                    = "log-bucket"
  s3_bucket_acl                     = "log-delivery-write"
  object_ownership                  = "ObjectWriter"
  versioning_enabled                = false
  transition_lifecycle_rule_enabled = false
  expiration_lifecycle_rule_enabled = false
  enforce_SSL_encryption_policy     = false
  use_aes256_encryption             = true
  force_destroy                     = local.in_development
  git_repository                    = var.git_repository

  attach_custom_bucket_policy = true
  policy                      = data.aws_iam_policy_document.log_bucket_policy_document.json
  kms_policy_to_attach        = data.aws_iam_policy_document.rs_mgmt_kms_key_policy.json
}


########################################################################################################################
###  Log Bucket Policy
########################################################################################################################

data "aws_iam_policy_document" "log_bucket_policy_document" {

  statement {
    sid    = "EnforceSSL"
    effect = "Deny"

    actions = ["s3:*"]


    principals {
      type        = "AWS"
      identifiers = ["*"]
    }

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }

    resources = ["${module.logs_bucket.s3_arn}/*"]
  }


  statement {
    sid    = "AllwOnlyThisArns"
    effect = "Allow"

    actions = ["s3:*"]

    principals {
      type = "AWS"
      identifiers = [
        "arn:aws:iam::${local.account_id}:root"
      ]
    }

    condition {
      test = "ArnLike"
      values = concat(local.access_arns,
        !local.in_production ? [data.aws_caller_identity.current.arn] : [],
        [
          data.aws_caller_identity.current.arn
      ])
      variable = "aws:PrincipalArn"
    }
    resources = [
      "${module.logs_bucket.s3_arn}/*",
      module.logs_bucket.s3_arn
    ]
  }
}



########################################################################################################################
###   Bucket for Lambda scripts
########################################################################################################################
module "lambda_scripts_bucket" {
  source = "git::ssh://git@github.mpi-internal.com/datastrategy-mobile-de/terraform-aws-s3-bucket-deployment//s3/s3-logging-encrypted?ref=tags/0.0.1"

  enable                        = true
  environment                   = var.stage
  project                       = var.project
  s3_bucket_name                = "lambda-script-bucket"
  s3_bucket_acl                 = "private"
  target_bucket_id              = module.logs_bucket.s3_bucket
  versioning_enabled            = true
  enforce_SSL_encryption_policy = true
  force_destroy                 = local.in_development
  git_repository                = var.git_repository

}

########################################################################################################################
###   Bucket for Redshift Schemas
########################################################################################################################
module "redshift_schema_bucket" {

  #checkov:skip=CKV_TF_1:Skip reason
  enable = true
  source = "git::ssh://git@github.mpi-internal.com/datastrategy-mobile-de/terraform-aws-s3-bucket-deployment.git//s3/s3-logging-encrypted?ref=tags/0.0.1"

  depends_on = [
    module.rs_mgmt_kms_key,
    module.lambda_scripts_bucket,
  ]

  environment                   = var.stage
  project                       = var.project
  git_repository                = var.git_repository
  s3_bucket_name                = "redshift-schema-bucket"
  s3_bucket_acl                 = "private"
  object_ownership              = "ObjectWriter"
  target_bucket_id              = module.logs_bucket.s3_bucket
  versioning_enabled            = false
  enforce_SSL_encryption_policy = false
  use_aes256_encryption         = false
  force_destroy                 = local.in_development
  create_kms_key                = false
  kms_key_arn                   = module.rs_mgmt_kms_key.kms_key_arn


  attach_custom_bucket_policy = true
  policy                      = data.aws_iam_policy_document.redshift_schema_bucket_policy_document.json
  kms_policy_to_attach        = data.aws_iam_policy_document.rs_mgmt_kms_key_policy.json
}

########################################################################################################################
###  redshift_schema Bucket Policy
########################################################################################################################

data "aws_iam_policy_document" "redshift_schema_bucket_policy_document" {

  statement {
    sid    = "EnforceSSL"
    effect = "Deny"

    actions = ["s3:*"]


    principals {
      type        = "AWS"
      identifiers = ["*"]
    }

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }

    resources = ["${module.redshift_schema_bucket.s3_arn}/*"]
  }

  statement {
    sid    = "AllwOnlyThisArns"
    effect = "Allow"

    actions = ["s3:*"]

    principals {
      type        = "AWS"
      identifiers = ["*"]
    }

    condition {
      test = "ArnLike"
      values = concat(local.access_arns,
        local.in_production ? [data.aws_caller_identity.current.arn] : [],
        [
          data.aws_caller_identity.current.arn,
          "arn:aws:iam::${local.account_id}:root",
          module.redshift_management_lambda.aws_lambda_function_role_arn,
      ])
      variable = "aws:PrincipalArn"
    }
    resources = [
      "${module.redshift_schema_bucket.s3_arn}/*",
      module.redshift_schema_bucket.s3_arn
    ]
  }
}


########################################################################################################################
###   Glue scripts bucket
########################################################################################################################
module "glue_scripts_bucket" {
  source = "git::ssh://git@github.mpi-internal.com/datastrategy-mobile-de/terraform-aws-s3-bucket-deployment//s3/s3-logging-encrypted?ref=tags/0.0.1"

  enable                        = true
  environment                   = var.stage
  project                       = var.project
  s3_bucket_name                = "glue-script-bucket"
  s3_bucket_acl                 = "private"
  target_bucket_id              = module.logs_bucket.s3_bucket
  versioning_enabled            = true
  enforce_SSL_encryption_policy = true
  force_destroy                 = local.in_development
  git_repository                = var.git_repository

}
#
#########################################################################################################################
####   Glue scripts bucket
#########################################################################################################################
#module "glue_scripts_bucket" {
#
#  #checkov:skip=CKV_TF_1:Skip reason
#  enable = true
#  source = "git::ssh://git@github.mpi-internal.com/datastrategy-mobile-de/terraform-aws-s3-bucket-deployment.git//s3/s3-logging-encrypted?ref=tags/0.0.1"
#
#  depends_on = [
#    module.rs_mgmt_kms_key,
#  ]
#
#  environment                   = var.stage
#  project                       = var.project
#  git_repository                = var.git_repository
#  s3_bucket_name                = "glue-script-bucket"
#  s3_bucket_acl                 = "private"
#  object_ownership              = "ObjectWriter"
#  target_bucket_id              = module.logs_bucket.s3_bucket
#  versioning_enabled            = false
#  enforce_SSL_encryption_policy = false
#  use_aes256_encryption         = false
#  force_destroy                 = local.in_development
#  create_kms_key                = false
#  kms_key_arn                   = module.rs_mgmt_kms_key.kms_key_arn
#
#
#  attach_custom_bucket_policy = true
#  policy                      = data.aws_iam_policy_document.glue_scripts_bucket_policy_document.json
#  kms_policy_to_attach        = data.aws_iam_policy_document.rs_mgmt_kms_key_policy.json
#}
#
#########################################################################################################################
####  Glue scripts bucket Policy
#########################################################################################################################
#
#data "aws_iam_policy_document" "glue_scripts_bucket_policy_document" {
#
#  statement {
#    sid    = "EnforceSSL"
#    effect = "Deny"
#
#    actions = ["s3:*"]
#
#
#    principals {
#      type        = "AWS"
#      identifiers = ["*"]
#    }
#
#    condition {
#      test     = "Bool"
#      variable = "aws:SecureTransport"
#      values   = ["false"]
#    }
#
#    resources = ["${module.glue_scripts_bucket.s3_arn}/*"]
#  }
#
#  statement {
#    sid    = "AllwOnlyThisArns"
#    effect = "Allow"
#
#    actions = ["s3:*"]
#
#    principals {
#      type        = "AWS"
#      identifiers = ["*"]
#    }
#
#    condition {
#      test = "ArnLike"
#      values = concat(local.access_arns,
#        local.in_production ? [data.aws_caller_identity.current.arn] : [],
#        [
#          data.aws_caller_identity.current.arn,
#          "arn:aws:iam::${local.account_id}:root",
#          module.rs_mgmt_glue_job.iam_role_arn,
#        ])
#      variable = "aws:PrincipalArn"
#    }
#    resources = [
#      "${module.glue_scripts_bucket.s3_arn}/*",
#      module.glue_scripts_bucket.s3_arn
#    ]
#  }
#}

########################################################################################################################
###   Bucket for glue data
########################################################################################################################
module "glue_data_bucket" {

  #checkov:skip=CKV_TF_1:Skip reason
  enable = true
  source = "git::ssh://git@github.mpi-internal.com/datastrategy-mobile-de/terraform-aws-s3-bucket-deployment.git//s3/s3-logging-encrypted?ref=tags/0.0.1"

  depends_on = [
    module.rs_mgmt_kms_key,
  ]

  environment                   = var.stage
  project                       = var.project
  git_repository                = var.git_repository
  s3_bucket_name                = "glue-data-bucket"
  s3_bucket_acl                 = "private"
  object_ownership              = "ObjectWriter"
  target_bucket_id              = module.logs_bucket.s3_bucket
  versioning_enabled            = false
  enforce_SSL_encryption_policy = false
  use_aes256_encryption         = false
  force_destroy                 = local.in_development
  create_kms_key                = false
  block_public_acls             = true
  kms_key_arn                   = module.rs_mgmt_kms_key.kms_key_arn


  attach_custom_bucket_policy = true
  policy                      = data.aws_iam_policy_document.glue_data_bucket_policy_document.json
  kms_policy_to_attach        = data.aws_iam_policy_document.rs_mgmt_kms_key_policy.json
}

########################################################################################################################
###  Glue Data Bucket Policy
########################################################################################################################

data "aws_iam_policy_document" "glue_data_bucket_policy_document" {

  #  statement {
  #    sid    = "EnforceSSL"
  #    effect = "Deny"
  #
  #    actions = ["s3:*"]
  #
  #
  #    principals {
  #      type        = "AWS"
  #      identifiers = ["*"]
  #    }
  #
  #    condition {
  #      test     = "Bool"
  #      variable = "aws:SecureTransport"
  #      values   = ["false"]
  #    }
  #
  #    resources = ["${module.glue_data_bucket.s3_arn}/*"]
  #  }

  statement {
    sid    = "AllwOnlyThisArns"
    effect = "Allow"

    actions = ["s3:*"]

    principals {
      type        = "AWS"
      identifiers = ["*"]
    }

    condition {
      test = "ArnLike"
      values = concat(local.access_arns,
        [
          data.aws_caller_identity.current.arn,
          "arn:aws:iam::${local.account_id}:root",
          module.rs_mgmt_glue_job.iam_role_arn,
          "arn:aws:iam::730335331410:role/data-platform-rs-pro-redshift-serverless-role",
          "arn:aws:iam::730335331410:role/datahub-s3-access-assume-role",
          module.ddr_copy_lambda.aws_lambda_function_role_arn,
          "arn:aws:iam::529745166931:role/unicron-mobilede-ds-pro-unicron-job",
          "arn:aws:iam::360928389411:role/glue-job-role"

      ])
      variable = "aws:PrincipalArn"
    }
    resources = [
      "${module.glue_data_bucket.s3_arn}/*",
      module.glue_data_bucket.s3_arn
    ]
  }
}


