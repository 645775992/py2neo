#!/usr/bin/env bash


# TODO: start/stop database
# TODO: check coverage is installed

coverage run -m unittest -vf
STATUS=$?
if [ "${STATUS}" == "0" ]
then
    coverage report -m
else
    exit ${STATUS}
fi
