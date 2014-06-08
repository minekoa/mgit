#!/usr/bin/env python
#-*- coding: shift_jis -*-
from mgitlib import *

import sys
import os
import os.path
import struct


if __name__ == '__main__':
    target = sys.argv[1]

    rf = open(target, 'rb')

    index = GitIndex()
    index.unpack(rf)

    for item in index.rows:
        print item
