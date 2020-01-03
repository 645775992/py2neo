#!/usr/bin/env bash

ARGS=$*
NEO4J_VERSIONS_FOR_JDK11="4.0 3.5"
NEO4J_VERSIONS_FOR_JDK8="3.4 3.3 3.2"


function run_unit_tests
{
    echo "Running unit tests"
    coverage run --append --module pytest -v ${ARGS} test/unit
    STATUS="$?"
    if [[ ${STATUS} -ne 0 ]]
    then
        exit ${STATUS}
    fi
}


function run_integration_tests
{
    NEO4J_VERSIONS=$1
    for NEO4J_VERSION in ${NEO4J_VERSIONS}
    do
        echo "Running standalone integration tests against Neo4j EE ${NEO4J_VERSION}"
        echo "Using Java installation at ${JAVA_HOME}"
        NEO4J_VERSION=${NEO4J_VERSION} coverage run --append --module pytest -v ${ARGS} test/integration
        STATUS="$?"
        if [[ ${STATUS} -ne 0 ]]
        then
            exit ${STATUS}
        fi
        if [[ "${PY2NEO_QUICK_TEST}" != "" ]]
        then
            return
        fi
    done
}


pip install --upgrade --quiet coverage pytest
pip install --upgrade --quiet -r requirements.txt -r test_requirements.txt
coverage erase

run_unit_tests

export JAVA_HOME="${HOME}/openjdk11"
if [ ! -d "${JAVA_HOME}" ]
then
    if [ -z "${TRAVIS_BUILD_DIR}" ]
    then
        install-jdk.sh --feature 11 --target "${JAVA_HOME}"
    else
        "${TRAVIS_BUILD_DIR}/install-jdk.sh" --feature 11 --target "${JAVA_HOME}"
    fi
    STATUS="$?"
    if [[ ${STATUS} -ne 0 ]]
    then
        echo "Failed to invoke install-jdk.sh"
        exit ${STATUS}
    fi
fi
run_integration_tests "${NEO4J_VERSIONS_FOR_JDK11}"

jdk_switcher use openjdk8
STATUS="$?"
if [[ ${STATUS} -ne 0 ]]
then
    echo "Failed to invoke jdk_switcher"
    exit ${STATUS}
fi
run_integration_tests "${NEO4J_VERSIONS_FOR_JDK8}"

coverage report
