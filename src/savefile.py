#!/usr/bin/env python
from mgitlib import *
import sys
import binascii

if __name__ == '__main__':
    target = sys.argv[1]

    db = GitDB()

    blob = GitBLOB()
    blob.putAway(open(target, 'r'))

    db.save(blob)

    print 'id    :', blob.getId()                # for debug             
    print '--------------------'                 # for debug
    print binascii.b2a_hex(blob.getContents())   # for debug
    print '--------------------'                 # for debug

