# Fetch the secret from AWS Secrets Manager
data "aws_secretsmanager_secret" "db_credentials" {
  name = "data_platform_rs_db"
}


data "aws_secretsmanager_secret_version" "db_credentials_version" {
  secret_id = data.aws_secretsmanager_secret.db_credentials.id
}

# parse the secret string into a map
locals {
  db_credentials = jsondecode(data.aws_secretsmanager_secret_version.db_credentials_version.secret_string)
}


