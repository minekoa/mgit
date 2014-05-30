from mgitlib import *
import sys

if __name__ == '__main__':
    target = sys.argv[1]

    db = GitDB()

    f = open(target, 'r')
    blob = GitBLOB()
    blob.genContent(f)
    blob.genId()

    db.save(blob)


