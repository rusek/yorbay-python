try:
    import coverage
except ImportError:
    pass
else:
    coverage.process_startup()

import os
import sys

DIR = os.path.dirname(os.path.abspath(__file__))

sys.path[:0] = [os.path.dirname(os.path.dirname(os.path.dirname(DIR)))]

import yorbay
from yorbay.exceptions import YorbayError

from sub.mod1 import tr as sub_mod1_tr
from sub.mod2 import tr as sub_mod2_tr

tr = yorbay.Context.from_module(__name__)

funcs = dict(
    sub_mod1_tr=sub_mod1_tr,
    sub_mod2_tr=sub_mod2_tr,
    tr=tr
)


def main():
    _, func, query = sys.argv

    try:
        result = funcs[func](query)
    except YorbayError as e:
        print '{0}.{1}:{2}'.format(e.__class__.__module__, e.__class__.__name__, e),
    else:
        print ':{0}'.format(result),


if __name__ == '__main__':
    main()
