#!/usr/bin/env python
#-*- coding: shift_jis -*-

from mgitlib import *
import sys


def mgit_add(file_path, db, index):

    # BLOB �̍쐬
    f = open(file_path, 'r')
    blob = GitBLOB()
    blob.putAway(f)
    f.close()

    blob.pack(db)

    # index �ɒǉ�
    index.append( file_path, blob.getId() )

if __name__ == '__main__':
    adding_files = sys.argv[1:]

    db     = GitDB()
    index  = GitIndex()
    with db.openIndexFile('rb') as rf:
        index.unpack(rf)

    for filepath in adding_files:
        mgit_add(filepath, db, index)

    with db.openIndexFile('wb') as wf:
        index.pack(wf)

