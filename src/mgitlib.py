#-*- coding: shift_jis -*-

import zlib
import hashlib
import struct
import os.path
import binascii

class GitObject(object):
    '''
    id      : �I�u�W�F�N�g�̓��e�� SHA1 �n�b�V�������l
    content : �I�u�W�F�N�g�̓��e�� zlib���k��������

    '''
    def getId(self):
        return self.id

    def getContent(self):
        return self.content

    def setContent(self, content):
        self.content = content

    def genId(self):
        self.id = hashlib.sha1(self.content).hexdigest()
        return self.id


class GitBLOB(GitObject):
    '''
    BLOB �� �I����������ł̃I�u�W�F�N�g
    '''

    def __init__(self, id=None):
        self.id      = id
        self.content = None

    def genContent(self, targetfile):
        '''
        �I�u�W�F�N�g�t�@�C���ɃV���A���C�Y�����̂�
        �����`���̃f�[�^�𐶐�����

        @param targetfile �Ώۂ̃t�@�C���I�u�W�F�N�g
        '''
        dat = targetfile.read()
        hdr = 'BLOB %d\0' % len(dat)
        self.content = zlib.compress(
                         struct.pack('< %ds %ds' % (len(hdr), len(dat)), 
                                     hdr, dat))
        return self.content

    def parseContent(self):
        deco_dat = zlib.decompress(self.content)

        # �w�b�_�����
        hdr_end_idx = deco_dat.find('\0')
        print hdr_end_idx
        otype = deco_dat[0:4]
        size  = deco_dat[4:hdr_end_idx]

        print 'type:', ''.join(otype)   # for debug
        print 'size:', size             # for debug

        # �f�[�^�����o��
        return deco_dat[hdr_end_idx+1:]

    def pack(self, db):
        '''GitObject�c���[�ɑ΂���ċA�Z�[�u'''
        # content �͂����o���Ă��� -> ID��������ăZ�[�u
        self.genId()
        db.save(self)

class FileAttr(object):
    TYPE_DIR      = 40   # �t�@�C�����: �f�B���N�g��
    TYPE_FILE     = 100  # �t�@�C�����: �t�@�C��
    TYPE_SLNK     = 120  # �t�@�C�����: �V���{���b�N�����N
    EXECUTABLE_OK = 644  # ���s�\��:   ���s�\
    EXECUTABLE_NG = 755  # ���s�\��:   ���s�s��

    def __init__(self, ftype=0, fexec=0):
        self.ftype = ftype
        self.fexec = fexec

    def parseString(self, finfo_str):
        fnum  = int(finfo_str)
        self.fexec = fnum % 1000
        self.ftype = fnum / 1000

    def asString(self):
        return '%d%03d' % (self.ftype,
                           self.fexec if self.ftype == FileAttr.TYPE_FILE else 0)

    def __str__(self):
        return self.asString()

    def isDirectory(self):
        return self.ftype == FileAttr.TYPE_DIR


class GitTree(GitObject):
    def __init__( self, id=None):
        self.id = id
        self.content  = None
        self.childlen = {}

    def appendChild( self, gitobj, f_name, f_attr ):
        self.childlen[f_name] = (gitobj, f_attr)
                                     
    def pack(self, db):
        '''GitObject�c���[�ɑ΂���ċA�Z�[�u'''

        # content �̍쐬
        body = ''
        for f_name, (gitobj, f_attr) in self.childlen.items():
            # �q�I�u�W�F�N�g�̃p�b�N (ID ���m�肷�邽��)
            gitobj.pack(db)

            # �I�u�W�F�N�g���X�g�s �ǉ�
            body += '%s %s \0 %s\n' % (f_attr.asString(), 
                                       f_name,
                                       gitobj.getId())
        hdr = 'TREE %d\0' % len(body)

        self.content = zlib.compress(
            struct.pack('< %ds %ds\n' % (len(hdr), len(body)), 
                        hdr, body))

        # ID �̍쐬
        self.genId()

        # �Z�[�u
        db.save(self)


class GitDB(object):
    def save(self, git_obj):
        path = os.path.join('.mgit/objects', git_obj.getId())
        f = open(path, "wb")
        f.write(git_obj.getContent())

#        print 'id:', git_obj.getId()                  # for debug
#        print '--------------------'                  # for debug
#        print binascii.b2a_hex(git_obj.getContent())  # for debug

        f.close()

    def load(self, git_obj_id, git_obj):
        path = os.path.join('.mgit/objects', git_obj_id)
        f = open(path, "rb")
        git_obj.setContent(f.read())

        print 'id:', git_obj_id                       # for debug
        print '--------------------'                  # for debug
        print binascii.b2a_hex(git_obj.getContent())  # for debug

        f.close()


