########################################################################################################################
###  Project generic vars
########################################################################################################################
variable "stage" {
  description = "Specify to which project this resource belongs, no default value to allow proper validation of project setup"
  default     = "dev"
}

variable "aws_region" {
  description = "Default Region"
  default     = "eu-central-1"
}

variable "project" {
  description = "Specify to which project this resource belongs"
  default     = "mo"
}


variable "project_id" {
  description = "project ID for billing"
  default     = "mo"
}

variable "git_repository" {
  description = "The current GIT repository used to keep track of the origin of resources in AWS"
  default     = "Not set"
}

variable "tag_KST" {
  description = "Kosten Stelle, tags"
  default     = "not set"
}

variable "default_lambda_handler" {
  description = "The name of the function handler inside main.py file"
  default     = "lambda_handler"
}

variable "redshift_schema_lambda_unique_function_name" {
  description = "The unique name of the function "
  default     = "redshift-schema"
}

variable "ddr_copy_lambda_unique_function_name" {
  description = "The unique name of the function "
  default     = "ddr-copy"
}

variable "ddr_delete_lambda_unique_function_name" {
  description = "The unique name of the function "
  default     = "ddr-delete"
}

variable "athena_consume_lambda_unique_function_name" {
  description = "The unique name of the function "
  default     = "athena-consume"
}

variable "lake_formation_permission_lambda_unique_function_name" {
  description = "The unique name of the function "
  default     = "lake-formation-permission"
}


