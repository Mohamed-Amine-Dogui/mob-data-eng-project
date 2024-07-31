########################################################################################################################
# State machine of the Step Function
########################################################################################################################
locals {
  ddr_state_machine_def = {
    Comment : "run the cdp glue job once a day",
    StartAt : "run_ddr_delete_lambda",
    States : {
      # Step 1: Run the the ddr_delete_lambda function
      run_ddr_delete_lambda : {
        Type : "Task",
        "Resource" : "arn:aws:states:::lambda:invoke",
        "Parameters" : {
          "FunctionName" : local.in_default_workspace ? module.ddr_delete_lambda.aws_lambda_function_arn : "",
          "Payload" : {
            "delete_sql_path" : "dl-mobilede-ds-platform-pro-datalake-xgukef6on6j2/mo-ddr-tasks/ddr-pro/20240406/parking_events/ParkingCreate/output/delete-queries",
          }
        },
        Catch : [{
          ErrorEquals : ["States.ALL"],
          Next : "run_ddr_copy_lambda"
        }],
        Next : "run_ddr_copy_lambda"
      },
      # Step 2: Run the the ddr_copy_lambda function
      run_ddr_copy_lambda : {
        Type : "Task",
        Resource : module.ddr_copy_lambda.aws_lambda_function_arn,
        Parameters : {
          "Payload" : {
            "source_s3_avro_path" : "dl-mobilede-ds-platform-pro-datalake-xgukef6on6j2/redshift-poc/ddr/20240413/ad_search_events/SvcAdSearch/append-to-bq"
          }
        },
        End : true
      }
    }
  }

}

########################################################################################################################
### Permissions of the Step Function
########################################################################################################################
data "aws_iam_policy_document" "ddr_step_functions_permissions" {

  statement {
    sid     = "AllowInvokeLambdaFunction"
    effect  = "Allow"
    actions = ["lambda:InvokeFunction"]
    resources = [
      module.ddr_delete_lambda.aws_lambda_function_arn,
      module.ddr_copy_lambda.aws_lambda_function_arn
    ]
  }
}

########################################################################################################################
### Step Function
########################################################################################################################
module "ddr_step_function" {
  enable                           = true
  source                           = "git::ssh://git@github.mpi-internal.com/datastrategy-mobile-de/terraform-aws-step-function-deployment.git?ref=tags/0.0.1"
  project                          = var.project
  git_repository                   = var.git_repository
  stage                            = var.stage
  state_machine_description        = "Orchestrate DDR Functions"
  aws_sfn_state_machine_definition = jsonencode(local.ddr_state_machine_def)
  state_machine_name               = "ddr-step-function"

  state_machine_schedule = [{
    name        = "Schedule",
    description = "state machine schedule",
    expression  = "cron(0 3 * * ? *)",
    input       = ""
  }]

  additional_policy        = data.aws_iam_policy_document.ddr_step_functions_permissions.json
  attach_additional_policy = true

}