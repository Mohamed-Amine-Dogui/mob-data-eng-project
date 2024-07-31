resource "aws_glue_catalog_database" "tf_delta_db" {
  name       = "mo_dev_delta_db"
  catalog_id = data.aws_caller_identity.current.account_id

}

resource "aws_lakeformation_permissions" "grant_admin_permissions" {

  principal = "arn:aws:iam::730335331410:role/aws-reserved/sso.amazonaws.com/eu-west-1/AWSReservedSSO_admin_11213697b25fc954"

  permissions                   = ["ALL"]
  permissions_with_grant_option = ["ALL"]

  database {
    catalog_id = data.aws_caller_identity.current.account_id
    name       = aws_glue_catalog_database.tf_delta_db.name
  }
}

# Register the S3 location as a Lake Formation resource and Role that has read/write access to the resource.
resource "aws_lakeformation_resource" "s3_data_location" {
  arn      = "arn:aws:s3:::mo-dev-glue-data-bucket/delta/ad_search"
  role_arn = module.glue_crawler.crawler_iam_role_arn
}


resource "aws_lakeformation_permissions" "grant_s3_crawler_permissions" {
  principal = module.glue_crawler.crawler_iam_role_arn

  data_location {
    arn = "arn:aws:s3:::mo-dev-glue-data-bucket/delta/ad_search"
  }

  permissions = ["DATA_LOCATION_ACCESS"]
}

resource "aws_lakeformation_permissions" "grant_db_permissions" {

  principal                     = module.glue_crawler.crawler_iam_role_arn
  permissions                   = ["CREATE_TABLE", "DESCRIBE"]
  permissions_with_grant_option = ["CREATE_TABLE", "DESCRIBE"]

  database {
    catalog_id = data.aws_caller_identity.current.account_id
    name       = aws_glue_catalog_database.tf_delta_db.name
  }
}



