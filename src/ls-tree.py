#!/usr/bin/env python
from mgitlib import *
import sys

if __name__ == '__main__':
    obj_id = sys.argv[1]

    db = GitDB()

        
    tree = GitTree()
    tree.unpack(db, obj_id)
        
    dat = '\n'.join( '%6s %s %s %s'  % 
                     (fattr.asString(), 
                      gitobj.getType(),
                      gitobj.getId(),
                      fname) 
                     for fname, (gitobj, fattr) 
                     in tree.childlen.items() )
                      
    print dat

