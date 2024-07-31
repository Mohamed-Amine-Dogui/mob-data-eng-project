#!/usr/bin/env bash

##############################################################################################
#
#   Utility functions that support CI/CD bureaucracies in lambda setups
#
#
##############################################################################################


installDependenciesLambda(){
    # params
    LAMBDA_NAME=${1}
    ROOT_DIR=${2}
    CLEANUP=${3:-true}
    PYTHON_VERSION=${4:-"3.9"}


    # Creation of variables for every needed directory level in the project.
    LAMBDA_DIR=${ROOT_DIR}/${LAMBDA_NAME}
    SRC_DIR=${LAMBDA_DIR}/src

    if [ -d $SRC_DIR ]; then
        printf "Found lambda dir. Proceeding."

        # Remove any possible previous virtualenv.
        cd ${LAMBDA_DIR} && rm -rf ${LAMBDA_NAME}_env && rm -rf ${LAMBDA_NAME}

        # Cleanup any previous code
        cd ${SRC_DIR} && find . | grep -v "lambda.py" | grep -v "main.py" | grep -v "lambda_modules" | grep -v "config.ini" | grep -v "libsnappy.so.1" | xargs rm -rf || echo finished cleaning src directory

        # Adding python dependencies to target (from virtual environment)
        PYTHON3_PATH=`which python${PYTHON_VERSION}`
        cd ${LAMBDA_DIR} && virtualenv -p $PYTHON3_PATH ${LAMBDA_NAME}_env
        printf "Successfully installed pip virtualenv (python ${PYTHON_VERSION}), sourcing it"

        cd ${LAMBDA_DIR} && source ${LAMBDA_NAME}_env/bin/activate
        # Installation all needed dependencies and libraries
        cd ${LAMBDA_DIR}
        for line in $(cat requirements.txt)
        do
          pip${PYTHON_VERSION} install $line
        done

        echo "copying all packages into src"

        cd ${LAMBDA_DIR} && cp -r ${LAMBDA_NAME}_env/lib/python${PYTHON_VERSION}/site-packages/* ${SRC_DIR} || cp -r ${LAMBDA_NAME}_env/lib/python${PYTHON_VERSION}/dist-packages/* ${SRC_DIR}

        echo "copying shared packages across lambda functions"
        mkdir -p ${SRC_DIR}/common && cp -r ${ROOT_DIR}/common/* ${SRC_DIR}/common/

        echo "Clean up"
        cd ${LAMBDA_DIR} && rm -rf ${LAMBDA_NAME}_env && rm -rf ${LAMBDA_NAME}

        if [ ${CLEANUP} = true ]; then
            echo "Making lambda slimmer..."
            # Cleanup unrequired packages for prod to slim the zip file size.
            if [ -d ${SRC_DIR}/__pycache__ ]; then
                rm -rf ${SRC_DIR}/__pycache__
            fi

            if [ -d ${SRC_DIR}/_pytest ]; then
                rm -rf ${SRC_DIR}/_pytest
            fi

            if ls ${SRC_DIR}/pip* 1> /dev/null 2>&1; then
                rm -r ${SRC_DIR}/pip*
            fi

            if ls ${SRC_DIR}/setuptools* 1> /dev/null 2>&1; then
                rm -r ${SRC_DIR}/setuptools*
            fi

            if ls ${SRC_DIR}/*.dist-info 1> /dev/null 2>&1; then
                rm -r ${SRC_DIR}/*.dist-info
            fi

        fi

        echo "################################"
        echo "Successfully finished assembling all packages from pip in the correct directory. You may now run make plan or make apply to zip your lambda and deploy remotely"
        echo "################################"

    else
       printf "\nERROR: Unable to build lambda funcion '$LAMBDA_NAME' -  provided path NOT found \n"
    fi
}
