#!/bin/bash

cd "$( dirname "$0" )/.."

export COVERAGE_PROCESS_START="$( pwd )/.coveragerc"
export COVERAGE_FILE="$( pwd )/.coverage"

coverage erase

coverage run ./scripts/run_tests.py ./tests/*/*.txt

for SCRIPT_FILE in ./tests/*_test.py
do
    coverage run "$SCRIPT_FILE"
done

coverage combine
coverage html
