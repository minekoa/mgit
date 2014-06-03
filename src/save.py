#-*- coding: shift_jis -*-
from mgitlib import *
import sys
import os
import os.path

if __name__ == '__main__':
    target = '.'
    tmp_dict = {}


    # 1. オブジェクトツリーの作成 -------------------------------
    for d_path, d_names, f_names in os.walk(target):
        if not tmp_dict.has_key(d_path):
            tmp_dict[d_path] = GitTree()
        curtree = tmp_dict[d_path]
        print '<%s>' % d_path           # for debug

        # mgit 管理フォルダはもちろん除外
        d_names[:] = [d for d in d_names if not d == '.mgit']

        # 子ファイル
        for f_name in f_names:
            f = open(os.path.join(d_path,f_name), 'r')
            blob = GitBLOB()
            blob.putAway(f)
            f.close()
            curtree.appendChild(blob, f_name, 
                                FileAttr( FileAttr.TYPE_FILE, FileAttr.EXECUTABLE_NG))
            print '  -%s' % f_name      # for debug

        # 子ディレクトリ
        for d_name in d_names:
            path = os.path.join(d_path, d_name)
            if not tmp_dict.has_key(path):
                tmp_dict[path] = GitTree()
            tree = tmp_dict[path]

            curtree.appendChild(tree, d_name, 
                                FileAttr( FileAttr.TYPE_DIR ) )
            print '  -%s/' % d_name    # for debug


    # 2. .mgit/objects にObjDBを保存 ----------------------------
    db = GitDB()

    root_tree = tmp_dict[target]
    root_tree.pack(db)

    print "ROOT_KEY:", root_tree.getId()


    # 3. HEADの情報を残す ---------------------------------------
    db.updateReference('HEAD', root_tree.getId())




