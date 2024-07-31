########################################################################################################################
## glue Crawler
########################################################################################################################
module "glue_crawler" {
  source = "git::ssh://git@github.mpi-internal.com/datastrategy-mobile-de/terraform-aws-glue-crawler-deployment.git?ref=tags/0.0.1"

  enable             = true
  crawler_name       = "tf-delta-crawler"
  glue_database_name = aws_glue_catalog_database.tf_delta_db.name #"mo-dev-delta-db"#module.glue_catalog_db.glue_database_name
  data_store_path    = "s3://mo-dev-glue-data-bucket/delta/ad_search/"
  table_prefix       = "delta_"
  #exclusion_pattern       = ["**/temporary/**", "**/backup/**"]

  crawler_schedule = "cron(0 12 * * ? *)"

  # Optional Inputs for Delta tables
  enable_delta_table        = true
  connection_name           = ""
  create_native_delta_table = true
  delta_tables              = ["s3://mo-dev-glue-data-bucket/delta/ad_search/"]
  write_manifest            = false

  stage      = var.stage
  project    = var.project
  project_id = var.project_id

  git_repository = var.git_repository

}


data "aws_iam_policy_document" "kms_policy" {
  statement {
    effect = "Allow"
    actions = [
      "kms:Decrypt",
      "kms:DescribeKey"
    ]
    resources = [
      module.rs_mgmt_kms_key.kms_key_arn
    ]
  }

}

resource "aws_iam_policy" "kms_policy" {
  name        = "kms-policy"
  description = "Policy for Glue crawler to access KMS and S3 resources"
  policy      = data.aws_iam_policy_document.kms_policy.json
}

resource "aws_iam_role_policy_attachment" "attach_kms_policy" {
  role       = module.glue_crawler.crawler_iam_role_name
  policy_arn = aws_iam_policy.kms_policy.arn
}
