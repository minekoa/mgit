#!/usr/bin/env python
#-*- coding: shift_jis -*-
from mgitlib import *
import sys
import os
import os.path
import time

def createGitTree(target):
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

        return tmp_dict[target]


if __name__ == '__main__':
    gitdb     = GitDB()
    gitconfig = GitConfig()

    # コミット時 対象 を取得
    root_tree = createGitTree('.')

    # 前のコミットオブジェクトを取得
    (ref_name, prv_obj_id) = gitdb.dereference('HEAD')

    if prv_obj_id != None:
        prev_commit = GitCommit()
        prev_commit.unpack(gitdb, prv_obj_id)
    else:
        prev_commit = None


    # コミット時の情報を生成・取得
#    msg = raw_input( 'commit message> ')
    msg = 'テストテスト'
    commit_info = CommitInfo()
    commit_info.setAuthorInfo( gitconfig.getUserInfo(), EpochTimeTz.now() )
    commit_info.setCommitInfo( gitconfig.getUserInfo(), EpochTimeTz.now() ,msg )


    # コミットオブジェクトの生成
    commit = GitCommit()
    commit.setCommitInfo(commit_info)
    commit.setRootTree(root_tree)
    if prev_commit != None:
        commit.setParentCommit(prev_commit)


    commit.pack(gitdb)
    print 'COMMIT: ', commit.getId()

    # 3. HEADの情報を残す ---------------------------------------
    gitdb.updateReference('HEAD', commit.getId())


