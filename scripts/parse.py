#!/usr/bin/env python

import json
import os
import sys

DIR = os.path.dirname(os.path.abspath(__file__))

sys.path[:0] = [os.path.dirname(DIR), os.path.join(DIR, 'lib')]

from yorbay.parser import parse_source
from yorbay_json import syntax_to_json


def main():
    print json.dumps(syntax_to_json(parse_source(sys.stdin.read())), indent=4)


if __name__ == '__main__':
    main()
