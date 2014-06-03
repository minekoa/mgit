from mgitlib import *
import sys

if __name__ == '__main__':
    obj_id = sys.argv[1]

    db = GitDB()

    blob = GitBLOB()
    db.load(obj_id, blob)

    fdat = blob.takeOut()

    print 'id  :', blob.getId()
    print '-----------------------'
    print fdat
    print '-----------------------'
