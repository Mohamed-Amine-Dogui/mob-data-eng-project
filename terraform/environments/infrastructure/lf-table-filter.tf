
module "lakeformation_table_filter" {
  source = "git::ssh://git@github.mpi-internal.com/datastrategy-mobile-de/terraform-aws-lakeformation-table-filter-deployment.git?ref=tags/0.0.1"

  enable         = true
  stage          = var.stage
  project        = var.project
  project_id     = var.project_id
  git_repository = var.git_repository

  filter_name      = "tf"
  database_name    = aws_glue_catalog_database.tf_delta_db.name
  table_name       = "delta_ad_search"
  excluded_columns = ["head__app", "head__id"]


  consumer_iam_role_arn = module.athena_consume_lambda.aws_lambda_function_role_arn


  depends_on = [aws_lakeformation_data_lake_settings.admin_settings]

}
