#!/usr/bin/env python

import json
import os
import sys

sys.path[0] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from yorbay.parser import parse_source


def main():
    print json.dumps(parse_source(sys.stdin.read()).to_json(), indent=4)


if __name__ == '__main__':
    main()
