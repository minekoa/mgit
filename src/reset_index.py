#!/usr/bin/env python
from mgitlib import *
import sys
import os.path


def reset_index(db, root_id):

    index  = GitIndex()

    roottree = GitTree()
    roottree.unpack(db, target_id)

    append_tree(roottree, '.', index)

    with db.openIndexFile('wb') as wf:
        index.pack(wf)


def append_tree(tree, dir_name,index):
    for f_name, (git_obj, f_attr) in tree.childlen.items():
        if f_attr.isFile():
            dispname = '%s/' % f_name if f_attr.isDirectory() else f_name
            index.append( os.path.join(dir_name, f_name), git_obj.getId() )

        if f_attr.isDirectory():
            append_tree(git_obj, os.path.join(dir_name, f_name), index)

if __name__ == '__main__':
    db     = GitDB()
    ref_path, target_id = db.dereference('HEAD')

    reset_index(db, target_id)
    
