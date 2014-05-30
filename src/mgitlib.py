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


class GitBLOB(GitObject):
    '''
    BLOB �� �I����������ł̃I�u�W�F�N�g
    '''

    def __init__(self, id=None):
        self.id      = id
        self.content = None

    def genId(self):
        self.id = hashlib.sha1(self.content).hexdigest()
        return self.id

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


class GitDB(object):
    def save(self, git_obj):
        path = os.path.join('.mgit/objects', git_obj.getId())
        f = open(path, "wb")
        f.write(git_obj.getContent())

        print 'id:', git_obj.getId()                  # for debug
        print '--------------------'                  # for debug
        print binascii.b2a_hex(git_obj.getContent())  # for debug

        f.close()

    def load(self, git_obj_id, git_obj):
        path = os.path.join('.mgit/objects', git_obj_id)
        f = open(path, "rb")
        git_obj.setContent(f.read())

        print 'id:', git_obj_id                       # for debug
        print '--------------------'                  # for debug
        print binascii.b2a_hex(git_obj.getContent())  # for debug

        f.close()


