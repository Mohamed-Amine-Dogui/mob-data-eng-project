resource "aws_lakeformation_data_lake_settings" "admin_settings" {

  admins = [
    "arn:aws:iam::730335331410:user/cicd_user",
    "arn:aws:iam::730335331410:role/aws-reserved/sso.amazonaws.com/eu-west-1/AWSReservedSSO_admin_11213697b25fc954",
    "arn:aws:iam::730335331410:role/mo-dev-tf-delta-crawler-role",
  ]

}

# Grant table permissions using Lake Formation
resource "aws_lakeformation_permissions" "table_permissions" {
  principal = "arn:aws:iam::730335331410:role/aws-reserved/sso.amazonaws.com/eu-west-1/AWSReservedSSO_admin_11213697b25fc954"

  permissions = [
    "SELECT",
    "ALTER",
    "DROP",
    "DELETE",
    "INSERT"
  ]

  permissions_with_grant_option = [
    "SELECT",
    "ALTER",
    "DROP",
    "DELETE",
    "INSERT"
  ]

  table {
    database_name = aws_glue_catalog_database.tf_delta_db.name
    name          = "delta_ad_search"
  }
}