#!/usr/bin/env python
from mgitlib import *
import sys

if __name__ == '__main__':
    obj_id = sys.argv[1]

    db = GitDB()

    (obj_type, size) = db.readObjHeader(obj_id)
    if obj_type == 'blob':
        blob = GitBLOB()
        db.load(obj_id, blob)
        dat = blob.takeOut()
        
    elif obj_type == 'tree':
        tree = GitTree()
        tree.unpack(db, obj_id)
        dat = '\n'.join( '%06s %s %s'  % 
                         (fattr.asString(), fname, gitobj.getId())
                         for fname, (gitobj, fattr) 
                         in tree.childlen.items())

    print 'type:', obj_type 
    print 'size:', size
    print 'id  :', obj_id
    print '-----------------------'
    print dat
    print '-----------------------'
