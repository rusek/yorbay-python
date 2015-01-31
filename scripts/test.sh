#!/bin/bash

DIR="$( cd "$( dirname "$0" )" && pwd )"

"$DIR/run_tests.py" "$DIR"/../tests/*/*.txt || exit $?

for SCRIPT_TEST in "$DIR"/../tests/*.py
do
    echo "Running $SCRIPT_TEST"
    "$SCRIPT_TEST" || exit $?
done
