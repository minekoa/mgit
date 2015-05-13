#!/usr/bin/env python
#-*- coding: shift_jis -*-
from mgitlib import *

import sys
import os
import os.path
import struct


if __name__ == '__main__':

    db     = GitDB()
    index  = GitIndex()
    with db.openIndexFile('rb') as rf:
        index.unpack(rf)

    print index
