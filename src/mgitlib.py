#-*- coding: shift_jis -*-

import zlib
import hashlib
import struct
import os.path
import binascii
import re
import datetime

class GitObject(object):
    '''
    id       : �I�u�W�F�N�g�̓��e�� SHA1 �n�b�V�������l
    contents : �I�u�W�F�N�g�̓��e�� zlib���k��������

    '''
    def getId(self):      return self.id
    def getContents(self): return self.contents

    def setId(self, obj_id):       self.id = obj_id
    def setContents(self, contents): self.contents = contents

    def genId(self, raw_contents):
        return hashlib.sha1(raw_contents).hexdigest()


class GitBLOB(GitObject):
    '''
    BLOB �� �I����������ł̃I�u�W�F�N�g

    <��BLOB> := <�w�b�_>\0<�{�f�B>
    <�w�b�_> := blob <�T�C�Y>
    <�{�f�B> := (�Ώۂ̃t�@�C���̓��e)
    <�T�C�Y> := (�\�i��������)
    '''

    def __init__(self, id=None):
        self.id       = id
        self.contents = None

    def putAway(self, targetfile):
        '''�Ώۃt�@�C����BLOB�ɂ��܂�����'''

        dat = targetfile.read()
        hdr = 'blob %d\0' % len(dat)
        raw_contents = struct.pack('< %ds %ds' % (len(hdr), len(dat)), 
                                  hdr, dat)
        self.id       = self.genId(raw_contents)
        self.contents = zlib.compress(raw_contents)

    def takeOut(self):
        '''BLOB�ɂ��܂����񂾃t�@�C�������o��'''
        deco_dat = zlib.decompress(self.contents)

        # �w�b�_�����
        hdr_end_idx = deco_dat.find('\0')
        otype = deco_dat[0:4]
        size  = deco_dat[4:hdr_end_idx]

        print 'type:', ''.join(otype)   # for debug
        print 'size:', size             # for debug

        # �f�[�^�����o��
        return deco_dat[hdr_end_idx+1:]

    def pack(self, db):
        '''GitObject�c���[�ɑ΂���ċA�Z�[�u'''
        db.save(self)

    def unpack(self, db, obj_id):
        '''GitObject�c���[�ɑ΂���ċA���[�h'''
        db.load(obj_id, self)
        return self


class GitTree(GitObject):
    '''
    TREE �� �I����������ł̃I�u�W�F�N�g

    <��TREE>      := <�w�b�_>\0<�{�f�B>
    <�w�b�_>      := tree <�T�C�Y>
    <�{�f�B>      := <�{�f�B1��>*
    <�{�f�B1��>   := <�t�@�C�����> <�t�@�C����>\0<�n�b�V���l>
    <�T�C�Y>      := (�\�i��������)
    <�t�@�C�����>:= (8�i��������, �ő�6��)
    <�n�b�V���l>  := (�o�C�i���A20byte)
    '''
    def __init__( self, id=None):
        self.id       = id
        self.contents = None
        self.childlen = {}

    def appendChild( self, gitobj, f_name, f_attr ):
        self.childlen[f_name] = (gitobj, f_attr)
                                     
    def pack(self, db):
        '''GitObject�c���[�ɑ΂���ċA�Z�[�u'''

        # contents �̍쐬
        body = ''
        for f_name, (gitobj, f_attr) in self.childlen.items():
            # �q�I�u�W�F�N�g�̃p�b�N (ID ���m�肷�邽��)
            gitobj.pack(db)

            # �I�u�W�F�N�g���X�g�s �ǉ� 
            finfo = '%s %s' % (f_attr.asString(), f_name)
            body += struct.pack('%ds c 20s' % len(finfo),
                                finfo, '\0', 
                                binascii.a2b_hex(gitobj.getId()))
        hdr = 'tree %d\0' % len(body)

        raw_contents = struct.pack('< %ds %ds\n' % (len(hdr), len(body)), 
                                  hdr, body)

        self.contents = zlib.compress(raw_contents)
        self.id       = self.genId(raw_contents)

        # �Z�[�u
        db.save(self)

    def unpack(self, db, obj_id):
        '''GitObject�c���[�ɑ΂���ċA���[�h'''
        db.load(obj_id, self)
        deco_dat = zlib.decompress(self.contents)

        # �w�b�_�����
        hdr_end_idx = deco_dat.find('\0')
        otype = deco_dat[0:4]
        size  = deco_dat[4:hdr_end_idx]

        # �f�[�^�����o��
        self.childlen = {}

        work = deco_dat[hdr_end_idx+1:]
        while True:
            if len(work.strip()) == 0: break

            f_type, f_name, obj_id, adv_len = self.parseOneChild(work)

            f_attr  = FileAttr().parseString(f_type)
            git_obj = GitTree() if f_attr.isDirectory() else GitBLOB()
            git_obj.unpack(db, binascii.b2a_hex(obj_id))

            self.appendChild(git_obj, f_name, f_attr)

            # advance next
            work = work[adv_len:]
        return self

    def parseOneChild(self, workstr):
        ftype_end = workstr.index(' ')
        fname_end = workstr.index('\0', ftype_end+1)
        objid_end = fname_end +1 +20

        ftype   = workstr[:ftype_end]
        fname   = workstr[ftype_end+1:fname_end]
        objid   = workstr[fname_end+1:objid_end]

        return (ftype, fname, objid, objid_end)


class FileAttr(object):
    TYPE_DIR      = 0o40   # �t�@�C�����: �f�B���N�g��
    TYPE_FILE     = 0o100  # �t�@�C�����: �t�@�C��
    TYPE_SLNK     = 0o120  # �t�@�C�����: �V���{���b�N�����N
    EXECUTABLE_OK = 0o644  # �p�[�~�b�V����:   ���s�\ (�� TYPE=FILE�̂ݎw���)
    EXECUTABLE_NG = 0o755  # �p�[�~�b�V����:   ���s�s�� (�� TYPE=FILE�̂ݎw���)

    def __init__(self, ftype=0, fexec=0):
        self.ftype = ftype
        self.fexec = fexec

    def parseString(self, finfo_str):
        fnum  = int(finfo_str,8)
        self.fexec = fnum % 0o1000
        self.ftype = fnum / 0o1000
        return self

    def asString(self):
        return '%o%03o' % (self.ftype,
                           self.fexec if self.ftype == FileAttr.TYPE_FILE else 0)

    def __str__(self):
        return self.asString()

    def isDirectory(self):
        return self.ftype == FileAttr.TYPE_DIR


class GitDB(object):

    #========================================
    # �I�u�W�F�N�gDB �̑���

    def save(self, git_obj):
        path = os.path.join('.mgit/objects', git_obj.getId())
        with open(path, "wb") as f:
            f.write(git_obj.getContents())

    def load(self, git_obj_id, git_obj):
        path = os.path.join('.mgit/objects', git_obj_id)
        with open(path, "rb") as f:
            git_obj.setId(git_obj_id)
            git_obj.setContents(f.read())

        f.close()


    #========================================
    # ���t�@�����X �̑���

    def dereference(self, ref_name):
        path = os.path.join('.mgit', ref_name)

        if not os.path.exists(path):
            return (ref_name, None)

        f   = open(path, 'r')
        dat = f.read()
        matobj = re.match(r"ref: (.*)", dat)
        f.close()

        if matobj != None:
            return self.dereference(matobj.group(1))
        else:
            return (ref_name, dat.strip())

    def updateReference(self, ref_name, git_obj_id):
        ref_path, old_obj_id = self.dereference(ref_name)

        # �ύX���Ȃ��ꍇ�͂Ȃɂ����Ȃ�
        if old_obj_id != None and old_obj_id == git_obj_id:
            return

        # ���t�@�����X�̎Q�Ɛ���X�V
        path = os.path.join('.mgit', ref_path)
        f = open(path, 'w')
        f.write(git_obj_id)
        f.close()

        
        # ���O���c��
        self._writeRefUpdateLog(ref_path, old_obj_id, git_obj_id )


    def _writeRefUpdateLog(self, ref_path, old_obj_id, git_obj_id):

        logpath = os.path.join('.mgit/logs', ref_path)
        if not os.path.exists(os.path.dirname(logpath)):
            os.makedirs(os.path.dirname(logpath))

        old_obj_id_str = old_obj_id if old_obj_id != None else '0'*40

        logfile = open(logpath, 'a')
        logfile.write( '%s %s %s\n' % (old_obj_id_str, git_obj_id,
                                       datetime.datetime.today().strftime("%Y%m%dT%H%M%S")))

