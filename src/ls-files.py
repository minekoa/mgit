#!/usr/bin/env python
#-*- coding: shift_jis -*-
from mgitlib import *

import sys
import os
import os.path
import struct


if __name__ == '__main__':
    rf = open('.mgit/index', 'rb')

    index = GitIndex()
    index.unpack(rf)

    for item in index.rows:
        print item



