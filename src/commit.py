#!/usr/bin/env python
#-*- coding: shift_jis -*-
from mgitlib import *
import sys
import os
import os.path
import time


def createTreeFromIndex(db, index):
    '''
    GitIndex ���� GitTree �؂𐶐�����
    '''

    # index ���� TREE�I�u�W�F�N�g���\�z
    tree_list = {}
    for pathname, index_row in index.rows.items():
        tree_path, fname = os.path.split(pathname)

        if not tree_list.has_key(tree_path):
            tree_list[tree_path] = GitTree()

        tree_list[tree_path].appendChild( createBLOB(db, index_row),
                                          fname,
                                          createFileAttr(db, index_row))


    # TREE�̃c���[�K�w���\�z
    for tree_path, tree_obj in tree_list.items():
        addToParent(tree_list, tree_path, tree_obj)

    # ���[�gTREE
    return tree_list[""]


def createBLOB(db, index_row):
    blob = GitBLOB()
    blob.unpack(db, index_row.obj_id)
    return blob


def createFileAttr(db, index_row):
    mode = index_row.st_mode

    fexec = FileAttr.EXECUTABLE_OK if mode & 0o700 else EXECUTABLE_NG
    ftype = FileAttr.TYPE_FILE    # �V���{���b�N�����N�̂��Ƃ͂Ƃ肠�����Y��Ă���
    
    return FileAttr(ftype, fexec)


def addToParent(tree_list, tree_path, tree_obj):
    '''
    tree_list ����eTREE �������āA�����Ɏ�TREE��ǉ�����B
    �i�e�c���[���Ȃ��Ƃ��͍��

    @note
    �����Ƀt�H���_�����Ȃ��t�H���_���L��ꍇ�A
    tree_list �ɐeTREE ���Ȃ���ԂɂȂ�
    '''

    # ���g�����[�gTREE�̏ꍇ�̓X�L�b�v
    if tree_path == "": return

    # �e�p�X���A���f�B���N�g�����𐶐�
    parent_tree_path, t_name = os.path.split(tree_path)

    # �eTREE���܂��ł��Ă��Ȃ������ꍇ�́A��ɂ������Еt����
    if not tree_list.has_key(parent_tree_path):
        tree_list[parent_tree_path] = GitTree()
        addToParent(tree_list,
                    parent_tree_path,
                    tree_list[parent_tree_path])
    
    # �eTREE �Ɏ�����ǉ�
    parent_tree = tree_list[tree_path]
    parent_tree.appendChild(tree_obj,
                            t_name,
                            FileAttr.directory())



if __name__ == '__main__':

    db = GitDB()
    gitconfig = GitConfig()


    # 1. index ���� Tree�I�u�W�F�N�g�𐶐� ----------------------
    index = GitIndex()
    with db.openIndexFile('rb') as rf:
        index.unpack(rf)
    root_tree = createTreeFromIndex(db, index)
    root_tree.pack(db) # new root_tree �� id �����߂����̂�
                       # �ЂƂ܂� pack����


    # 2. Commit �I�u�W�F�N�g�̐��� ------------------------------
    # �O�̃R�~�b�g�I�u�W�F�N�g���擾
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


    # �R�~�b�g���̏��𐶐��E�擾
#    msg = raw_input( 'commit message> ')
    msg = '�e�X�g�e�X�g'
    commit_info = CommitInfo()
    commit_info.setAuthorInfo( gitconfig.getUserInfo(), EpochTimeTz.now() )
    commit_info.setCommitInfo( gitconfig.getUserInfo(), EpochTimeTz.now() ,msg )


    # �R�~�b�g�I�u�W�F�N�g�̐���
    commit = GitCommit()
    commit.setCommitInfo(commit_info)
    commit.setRootTree(root_tree)
    if prev_commit != None:
        commit.setParentCommit(prev_commit)


    # 3. DB �ɃZ�[�u --------------------------------------------
    commit.pack(db)
    print 'COMMIT: ', commit.getId()


    # 4. HEAD�̏����c�� ---------------------------------------
    db.updateReference('HEAD', commit.getId())


