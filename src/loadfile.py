from mgitlib import *
import sys

if __name__ == '__main__':
    obj_id = sys.argv[1]

    db = GitDB()

    blob = GitBLOB()
    db.load(obj_id, blob)


    blob.genId()
    fdat = blob.parseContent()

    print 'id:'
    print '  old  :', obj_id
    print '  renew:', blob.getId()
    print '-----------------------'
    print fdat


