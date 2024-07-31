#
#output "aws_iam_role_PA_LIMITEDDEV_arn" {
#  value = data.aws_iam_role.PA_LIMITEDDEV.arn
#}
#
#output "aws_iam_role_PA_CAS_demo_DATA_SCIENTIST_arn" {
#  value = data.aws_iam_role.PA_CAS_demo_DATA_SCIENTIST.arn
#}
#
#output "aws_iam_role_PA_CAP_demo_DATA_SCIENTIST_arn" {
#  value = data.aws_iam_role.PA_CAP_demo_DATA_SCIENTIST.arn
#}
#
#########################################################################################################################
## Common Storage outputs
#########################################################################################################################
#
#output "glue_scripts_bucket_name" {
#  value = module.demo_glue_scripts_bucket.s3_bucket
#}
#
#output "glue_scripts_bucket_arn" {
#  value = module.demo_glue_scripts_bucket.s3_arn
#}
#
#output "glue_scripts_bucket_kms_key_arn" {
#  value = module.demo_glue_scripts_bucket.aws_kms_key_arn
#}
#
#output "source_code_bucket_name" {
#  value = module.source_code_bucket.s3_bucket
#}
#
#output "source_code_bucket_arn" {
#  value = module.source_code_bucket.s3_arn
#}
#
#output "source_code_bucket_kms_key_arn" {
#  value = module.source_code_bucket.aws_kms_key_arn
#}
#
#########################################################################################################################
## FSAG outputs
#########################################################################################################################
#output "fsag_lambda_pull_kms_key_arn" {
#  value = module.fsag_cap_pull_lambda_kms_key.kms_key_arn
#}
#
#output "fsag_lambda_pull_role_arn" {
#  value = module.fsag_cap_pull_lambda.aws_lambda_function_role_arn
#}
#
#output "fsag_lambda_pull_role_name" {
#  value = module.fsag_cap_pull_lambda.aws_lambda_function_role_name
#}
#
#output "fsag_step_function_sfn_arn" {
#  value = module.fsag_step_function.aws_sfn_state_machine_arn
#}
#
#output "fsag_target_data_bucket_arn" {
#  value = module.fsag_target_data_bucket.s3_arn
#}
#
#output "fsag_target_data_bucket_name" {
#  value = module.fsag_target_data_bucket.s3_bucket
#}
#
#output "fsag_target_data_bucket_kms_key_arn" {
#  value = module.fsag_target_data_bucket.aws_kms_key_arn
#}
#
#
#########################################################################################################################
## onecrm-campaign-cockpit outputs
#########################################################################################################################
#output "onecrm_campaign_cockpit_step_function_sfn_arn" {
#  value = module.onecrm_campaign_cockpit_step_function.aws_sfn_state_machine_role_arn
#}
#
#output "onecrm_campaign_cockpit_step_function_sfn_name" {
#  value = module.onecrm_campaign_cockpit_step_function.aws_sfn_state_machine_name
#}
#
#output "onecrm_campaign_cockpit_glue_iam_role_arn" {
#  value = module.onecrm_campaign_cockpit_glue_job.iam_role_arn
#}
#
#output "onecrm_campaign_cockpit_target_data_bucket_name" {
#  value = module.onecrm_campaign_cockpit_target_data_bucket.s3_bucket
#}
#
#output "onecrm_campaign_cockpit_target_data_bucket_kms_key_arn" {
#  value = module.onecrm_campaign_cockpit_target_data_bucket.aws_kms_key_arn
#}
#
#########################################################################################################################
####  Fstream outputs
#########################################################################################################################
#
#output "fstream_s3_bucket_arn" {
#  value = module.fstream_api_data_bucket.s3_arn
#}
#
#output "fstream_s3_bucket_kms_key_id" {
#  value = module.fstream_api_data_bucket.aws_kms_key_id
#}
#
#output "fstream_lambda_arn" {
#  value = module.fstream_sqs_s3_lambda.aws_lambda_function_arn
#}
#
#output "fstream_lambda_kms_key_arn" {
#  value = module.fstream_sqs_s3_lambda.aws_lambda_function_kms_key_arn
#}
#
#output "fstream_lambda_role_arn" {
#  value = module.fstream_sqs_s3_lambda.aws_lambda_function_role_arn
#}
#
#output "fstream_lambda_invoke_arn" {
#  value = module.fstream_sqs_s3_lambda.aws_lambda_function_invoke_arn
#}
#
#
#output "fstream_glue_iam_role_arn" {
#  value = module.fstream_glue_job.iam_role_arn
#}
#
#output "fstream_s3_bucket_name" {
#  value = module.fstream_api_data_bucket.s3_bucket
#}
#
#output "fstream_s3_bucket_kms_key_arn" {
#  value = module.fstream_api_data_bucket.aws_kms_key_arn
#}
#
