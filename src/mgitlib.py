#-*- coding: shift_jis -*-

import zlib
import hashlib
import struct
import os.path
import binascii

class GitObject(object):
    def getId(self):
        return self.id

    def getContent(self):
        return self.content

class GitBLOB(GitObject):
    '''
    BLOB の オンメモリ上でのオブジェクト
    '''

    def __init__(self, id=None):
        self.id      = id
        self.content = None

    def genId(self):
        self.id = hashlib.sha1(self.content).hexdigest()
        return self.id

    def genContent(self, targetfile):
        '''
        オブジェクトファイルにシリアライズされるのと
        同じ形式のデータを生成する

        @param targetfile 対象のファイルオブジェクト
        '''
        dat = targetfile.read()
        hdr = 'BLOB %d\0' % len(dat)
        self.content = zlib.compress(
                         struct.pack('< %ds %ds' % (len(hdr), len(dat)), 
                                     hdr, dat))
        return self.content

class GitDB(object):
    def save(self, git_obj):
        path = os.path.join('.mgit/objects', git_obj.getId())
        f = open(path, "wb")
        f.write(git_obj.getContent())

        print 'id:', git_obj.getId()                  # for debug
        print '--------------------'                  # for debug
        print binascii.b2a_hex(git_obj.getContent())  # for debug

        f.close()


