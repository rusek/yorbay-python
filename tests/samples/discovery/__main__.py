try:
    import coverage
except ImportError:
    pass
else:
    coverage.process_startup()

import sys


import yorbay
from yorbay.exceptions import YorbayError

from sub.mod1 import tr as sub_mod1_tr
from sub.mod2 import tr as sub_mod2_tr
from sub.sub3 import tr as sub_sub3_tr
from sub.sub3.mod import tr as sub_sub3_mod_tr

tr = yorbay.Context.from_module(__name__)

funcs = dict(
    sub_mod1_tr=sub_mod1_tr,
    sub_mod2_tr=sub_mod2_tr,
    sub_sub3_tr=sub_sub3_tr,
    sub_sub3_mod_tr=sub_sub3_mod_tr,
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
