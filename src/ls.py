from mgitlib import *
import sys

def ls_tree(tree, indent):
    for f_name, (git_obj, f_attr) in tree.childlen.items():
        dispname = '%s/' % f_name if f_attr.isDirectory() else f_name

        print ' ' * indent, '+--' , dispname,
        print ' ' * (30 - len(dispname) - indent),
        print git_obj.getId()

        if f_attr.isDirectory():
            ls_tree(git_obj, indent + 2)

if __name__ == '__main__':
    db     = GitDB()
    ref_path, target_id = db.dereference('HEAD')

    tree = GitTree()
    tree.unpack(db, target_id)

    print '+-- /', ' ' * (30), tree.getId()
    ls_tree(tree, 1)
