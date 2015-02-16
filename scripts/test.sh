#!/bin/bash

DIR="$( cd "$( dirname "$0" )" && pwd )"

"$DIR/run_tests.py" "$DIR"/../tests/*/*.txt || exit $?
"$DIR/run_tests.py" --use-debug "$DIR"/../tests/*/*.txt || exit $?

for SCRIPT_TEST in "$DIR"/../tests/*_test.py
do
    echo "Running $SCRIPT_TEST"
    "$SCRIPT_TEST" || exit $?
done
