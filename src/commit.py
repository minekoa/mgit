#!/usr/bin/env python
#-*- coding: shift_jis -*-
from mgitlib import *
import sys
import os
import os.path
import time


def createTreeFromIndex(db, index):
    '''
    GitIndex から GitTree 木を生成する
    '''

    # index から TREEオブジェクトを構築
    tree_list = {}
    for pathname, index_row in index.rows.items():
        tree_path, fname = os.path.split(pathname)

        if not tree_list.has_key(tree_path):
            tree_list[tree_path] = GitTree()

        tree_list[tree_path].appendChild( createBLOB(db, index_row),
                                          fname,
                                          createFileAttr(db, index_row))


    # TREEのツリー階層を構築
    for tree_path, tree_obj in tree_list.items():
        addToParent(tree_list, tree_path, tree_obj)

    # ルートTREE
    return tree_list[""]


def createBLOB(db, index_row):
    blob = GitBLOB()
    blob.unpack(db, index_row.obj_id)
    return blob


def createFileAttr(db, index_row):
    mode = index_row.st_mode

    fexec = FileAttr.EXECUTABLE_OK if mode & 0o700 else EXECUTABLE_NG
    ftype = FileAttr.TYPE_FILE    # シンボリックリンクのことはとりあえず忘れておく
    
    return FileAttr(ftype, fexec)


def addToParent(tree_list, tree_path, tree_obj):
    '''
    tree_list から親TREE を見つけて、そこに自TREEを追加する。
    （親ツリーがないときは作る

    @note
    直下にフォルダしかないフォルダが有る場合、
    tree_list に親TREE いない状態になる
    '''

    # 自身がルートTREEの場合はスキップ
    if tree_path == "": return

    # 親パス名、自ディレクトリ名を生成
    parent_tree_path, t_name = os.path.split(tree_path)

    # 親TREEがまだできていなかった場合は、先にそちらを片付ける
    if not tree_list.has_key(parent_tree_path):
        tree_list[parent_tree_path] = GitTree()
        addToParent(tree_list,
                    parent_tree_path,
                    tree_list[parent_tree_path])
    
    # 親TREE に自分を追加
    parent_tree = tree_list[tree_path]
    parent_tree.appendChild(tree_obj,
                            t_name,
                            FileAttr.directory())



if __name__ == '__main__':

    db = GitDB()
    gitconfig = GitConfig()


    # 1. index から Treeオブジェクトを生成 ----------------------
    index = GitIndex()
    with db.openIndexFile('rb') as rf:
        index.unpack(rf)
    root_tree = createTreeFromIndex(db, index)
    root_tree.pack(db) # new root_tree の id を求めたいので
                       # ひとまず packする


    # 2. Commit オブジェクトの生成 ------------------------------
    # 前のコミットオブジェクトを取得
    (ref_name, prv_obj_id) = db.dereference('HEAD')

    if prv_obj_id != None:
        prev_commit = GitCommit()
        prev_commit.unpack(db, prv_obj_id)
    else:
        prev_commit = None

    if prev_commit.root_tree.id == root_tree.id:
        print '= Nothing Update ='
        exit(0)

    print 'prev_tree:', prev_commit.root_tree.id # for debug
    print 'new_tree :', root_tree.id             # for debug


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


    # 3. DB にセーブ --------------------------------------------
    commit.pack(db)
    print 'COMMIT: ', commit.getId()


    # 4. HEADの情報を残す ---------------------------------------
    db.updateReference('HEAD', commit.getId())


