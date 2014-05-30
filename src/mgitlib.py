#-*- coding: shift_jis -*-

import zlib
import hashlib
import struct
import os.path
import binascii
import re

class GitObject(object):
    '''
    id      : オブジェクトの内容を SHA1 ハッシュした値
    content : オブジェクトの内容を zlib圧縮したもの

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
    BLOB の オンメモリ上でのオブジェクト
    '''

    def __init__(self, id=None):
        self.id      = id
        self.content = None

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

    def parseContent(self):
        deco_dat = zlib.decompress(self.content)

        # ヘッダを解析
        hdr_end_idx = deco_dat.find('\0')
        print hdr_end_idx
        otype = deco_dat[0:4]
        size  = deco_dat[4:hdr_end_idx]

        print 'type:', ''.join(otype)   # for debug
        print 'size:', size             # for debug

        # データを取り出し
        return deco_dat[hdr_end_idx+1:]

    def pack(self, db):
        '''GitObjectツリーに対する再帰セーブ'''
        # content はもう出来ている -> IDだけ作ってセーブ
        self.genId()
        db.save(self)

    def unpack(self, db, obj_id):
        '''GitObjectツリーに対する再帰ロード'''
        db.load(obj_id, self)
        self.genId()


class FileAttr(object):
    TYPE_DIR      = 40   # ファイル種別: ディレクトリ
    TYPE_FILE     = 100  # ファイル種別: ファイル
    TYPE_SLNK     = 120  # ファイル種別: シンボリックリンク
    EXECUTABLE_OK = 644  # 実行可能か:   実行可能
    EXECUTABLE_NG = 755  # 実行可能か:   実行不可

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
        '''GitObjectツリーに対する再帰セーブ'''

        # content の作成
        body = ''
        for f_name, (gitobj, f_attr) in self.childlen.items():
            # 子オブジェクトのパック (ID を確定するため)
            gitobj.pack(db)

            # オブジェクトリスト行 追加
            body += '%s %s \0 %s\n' % (f_attr.asString(), 
                                       f_name,
                                       gitobj.getId())
        hdr = 'TREE %d\0' % len(body)

        self.content = zlib.compress(
            struct.pack('< %ds %ds\n' % (len(hdr), len(body)), 
                        hdr, body))

        # ID の作成
        self.genId()

        # セーブ
        db.save(self)


    def unpack(self, db, obj_id):
        '''GitObjectツリーに対する再帰ロード'''
        db.load(obj_id, self)
        deco_dat = zlib.decompress(self.content)

        # ヘッダを解析
        hdr_end_idx = deco_dat.find('\0')
        otype = deco_dat[0:4]
        size  = deco_dat[4:hdr_end_idx]

        # データを取り出し
        self.childlen = {}
        for item in deco_dat[hdr_end_idx+1:].split('\n'):
            if item == '': continue

            (attr_and_name, git_obj_id) = item.split('\0')
            idx = attr_and_name.find(' ')
            f_attr_str, f_name = (attr_and_name[0:idx], attr_and_name[idx+1:])

            f_attr = FileAttr()
            f_attr.parseString(f_attr_str)
        
            git_obj = GitTree() if f_attr.isDirectory() else GitBLOB()
            git_obj.unpack(db, git_obj_id.strip())

            self.appendChild(git_obj, f_name.strip(), f_attr)

        self.genId()


class GitDB(object):

    #========================================
    # オブジェクトDB の操作

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

#        print 'id:', git_obj_id                       # for debug
#        print '--------------------'                  # for debug
#        print binascii.b2a_hex(git_obj.getContent())  # for debug

        f.close()


    #========================================
    # リファレンス の操作

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

        # 変更がない場合はなにもしない
        if old_obj_id != None and old_obj_id == git_obj_id:
            return

        # リファレンスの参照先を更新
        path = os.path.join('.mgit', ref_path)
        f = open(path, 'w')
        f.write(git_obj_id)
        f.close()

        
        # ログを残す
        self._writeRefUpdateLog(ref_path, old_obj_id, git_obj_id )


    def _writeRefUpdateLog(self, ref_path, old_obj_id, git_obj_id):

        logpath = os.path.join('.mgit/logs', ref_path)
        if not os.path.exists(os.path.dirname(logpath)):
            os.makedirs(os.path.dirname(logpath))

        old_obj_id_str = old_obj_id if olf_obj_id != None else '0'*40

        logfile = open(logpath, 'a')
        logfile.write( '%s %s %s\n' % (old_obj_id_str, git_obj_id,
                                       datetime.datetime.today().strftime("%Y%m%dT%H%M%S")))

