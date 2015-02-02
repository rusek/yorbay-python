#!/bin/bash

cd "$( dirname "$0" )/.."

coverage erase

coverage run -a ./scripts/run_tests.py ./tests/*/*.txt

for SCRIPT_FILE in ./tests/*_test.py
do
    coverage run -a "$SCRIPT_FILE"
done

coverage html
