#!/usr/bin/env bash

set -e -x

# PATH
LAMBDA_NAME=$(basename "${PWD}")
LAMBDAS_DIR=$(dirname "${PWD}")

echo "Building ${LAMBDA_NAME} Lambda..."

# load common funcs
source ${LAMBDAS_DIR}/common_bash/build.sh


installDependenciesLambda ${LAMBDA_NAME} ${LAMBDAS_DIR} true "3.9"
