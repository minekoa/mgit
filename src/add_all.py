#!/usr/bin/env python
#-*- coding: shift_jis -*-
from mgitlib import *

import sys
import os
import os.path
import struct


if __name__ == '__main__':
    target = '.'
    index = GitIndex()

    for d_path, d_names, f_names in os.walk(target):
        print '<%s>' % d_path           # for debug

        # mgit 管理フォルダはもちろん除外
        d_names[:] = [d for d in d_names if not d == '.mgit']

        # 子ファイル
        for f_name in f_names:
            path_name = os.path.join(d_path,f_name)

            f = open(path_name, 'r')
            blob = GitBLOB()
            blob.putAway(f)
            f.close()

            index.append(path_name, blob.getId())
           
    wf = open('.mgit/index', 'wb')
    index.pack(wf)

