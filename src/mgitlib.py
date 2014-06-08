#!/usr/bin/env python
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
    id       : オブジェクトの内容を SHA1 ハッシュした値
    contents : オブジェクトの内容を zlib圧縮したもの

    '''
    def getId(self):      return self.id
    def getContents(self): return self.contents

    def setId(self, obj_id):       self.id = obj_id
    def setContents(self, contents): self.contents = contents

    def genId(self, raw_contents):
        return hashlib.sha1(raw_contents).hexdigest()


class GitBLOB(GitObject):
    '''
    BLOB の オンメモリ上でのオブジェクト

    <生BLOB> := <ヘッダ>\0<ボディ>
    <ヘッダ> := blob <サイズ>
    <ボディ> := (対象のファイルの内容)
    <サイズ> := (十進数文字列)
    '''

    def __init__(self, id=None):
        self.id       = id
        self.contents = None

    def getType(self): return 'blob'

    def putAway(self, targetfile):
        '''対象ファイルをBLOBにしまい込む'''

        dat = targetfile.read()
        hdr = 'blob %d\0' % len(dat)
        raw_contents = struct.pack('> %ds %ds' % (len(hdr), len(dat)), 
                                  hdr, dat)
        self.id       = self.genId(raw_contents)
        self.contents = zlib.compress(raw_contents)

    def takeOut(self):
        '''BLOBにしまい込んだファイルを取り出す'''
        deco_dat = zlib.decompress(self.contents)

        # ヘッダを解析
        hdr_end_idx = deco_dat.find('\0')
        otype = deco_dat[0:4]
        size  = deco_dat[4:hdr_end_idx]

#        print 'type:', ''.join(otype)   # for debug
#        print 'size:', size             # for debug

        # データを取り出し
        return deco_dat[hdr_end_idx+1:]

    def pack(self, db):
        '''GitObjectツリーに対する再帰セーブ'''
        db.save(self)

    def unpack(self, db, obj_id):
        '''GitObjectツリーに対する再帰ロード'''
        db.load(obj_id, self)
        return self


class GitTree(GitObject):
    '''
    TREE の オンメモリ上でのオブジェクト

    <生TREE>      := <ヘッダ>\0<ボディ>
    <ヘッダ>      := tree <サイズ>
    <ボディ>      := <ボディ1件>*
    <ボディ1件>   := <ファイル種別> <ファイル名>\0<ハッシュ値>
    <サイズ>      := (十進数文字列)
    <ファイル種別>:= (8進数文字列, 最大6桁)
    <ハッシュ値>  := (バイナリ、20byte)
    '''
    def __init__( self, id=None):
        self.id       = id
        self.contents = None
        self.childlen = {}

    def getType(self): return 'tree'

    def appendChild( self, gitobj, f_name, f_attr ):
        self.childlen[f_name] = (gitobj, f_attr)
                                     
    def pack(self, db):
        '''GitObjectツリーに対する再帰セーブ'''

        # contents の作成
        body = ''
        for f_name, (gitobj, f_attr) in self.childlen.items():
            # 子オブジェクトのパック (ID を確定するため)
            gitobj.pack(db)

            # オブジェクトリスト行 追加 
            finfo = '%s %s' % (f_attr.asString(), f_name)
            body += struct.pack('>%ds c 20s' % len(finfo),
                                finfo, '\0', 
                                binascii.a2b_hex(gitobj.getId()))
        hdr = 'tree %d\0' % len(body)

        raw_contents = struct.pack('> %ds %ds\n' % (len(hdr), len(body)), 
                                  hdr, body)

        self.contents = zlib.compress(raw_contents)
        self.id       = self.genId(raw_contents)

        # セーブ
        db.save(self)

    def unpack(self, db, obj_id):
        '''GitObjectツリーに対する再帰ロード'''
        db.load(obj_id, self)
        deco_dat = zlib.decompress(self.contents)

        # ヘッダを解析
        hdr_end_idx = deco_dat.find('\0')
        otype = deco_dat[0:4]
        size  = deco_dat[4:hdr_end_idx]

        # データを取り出し
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
    TYPE_DIR      = 0o40   # ファイル種別: ディレクトリ
    TYPE_FILE     = 0o100  # ファイル種別: ファイル
    TYPE_SLNK     = 0o120  # ファイル種別: シンボリックリンク
    EXECUTABLE_OK = 0o644  # パーミッション:   実行可能 (※ TYPE=FILEのみ指定可)
    EXECUTABLE_NG = 0o755  # パーミッション:   実行不可 (※ TYPE=FILEのみ指定可)

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


class GitIndex(object):
    def __init__(self):
        self.rows = []

    def append(self, pathname, obj_id):
        self.rows.append( GitIndexRow(pathname, obj_id))

    def pack(self, wf):
        wf.write(struct.pack( ">4s L L",
                              'DISC', 2, len(self.rows)))
        for row in self.rows:
            row.pack(wf)

    def unpack(self, rf):
        sig, ver, f_cnt = struct.unpack(">4s L L",
                                        rf.read(4*3))
        print 'sig :', sig           # for debug
        print 'ver : %04d' % ver     # for debug
        print 'cnt : %04x' % f_cnt   # for debug

        if ver != 2:
            raise ValueError('Not Supoort Format %d' % ver)

        for i in range(0, f_cnt):
            tmp = GitIndexRow()
            tmp.unpack(rf)
            self.rows.append(tmp)


        if f_cnt != len(self.rows):
            print "ERROR ! unpack failed %d != %d" % (f_cnt, len(self.rows))


class GitIndexRow(object):
    def __init__(self, pathname='', obj_id=''):
        self.pathname = pathname.replace(os.path.sep, '/')
        if self.pathname[0:2] == './':
            self.pathname = self.pathname[2:]

        self.obj_id   = obj_id

        if self.pathname != '':
            self.loadFileStatus(self.pathname)

    def loadFileStatus(self, pathname):
        statinfo = os.stat(pathname)
        self.st_ctime   = statinfo.st_ctime
        self.st_ctime_n = 0
        self.st_mtime   = statinfo.st_mtime
        self.st_mtime_n = 0
        self.st_dev     = statinfo.st_dev
        self.st_ino     = statinfo.st_ino
        self.st_mode    = statinfo.st_mode
        self.st_uid     = statinfo.st_uid
        self.st_gid     = statinfo.st_gid
        self.st_size    = statinfo.st_size


    def pack(self, wf):
        # ctime(sec) ctime(nanosec) mtime(sec) mtime(nanosec)
        wf.write(struct.pack(">L L L L",
                             self.st_ctime, 0, 
                             self.st_mtime, 0))
                
        # dev inode mode uid gid size
        wf.write(struct.pack(">L L L L L L",
                             self.st_dev,
                             self.st_ino,
                             self.st_mode,
                             self.st_uid,
                             self.st_gid,
                             self.st_size))

        # SHA1_hash
        wf.write(struct.pack(">20s",
                             binascii.a2b_hex(self.obj_id)))

        # name & langth
        pathname_len = len(self.pathname)
        wf.write(struct.pack(">H", pathname_len))
        wf.write(struct.pack(">%ds" % pathname_len, self.pathname))

        # padding
        padding_len  = (8 - (pathname_len -2) % 8) if (pathname_len -2) % 8 != 0 else 8
        wf.write(struct.pack(">%ds" % padding_len, '\0' * padding_len))

    def unpack(self, rf):
        self.st_ctime, self.st_ctime_n         = struct.unpack(">L L", rf.read(4 *2))
        self.st_mtime, self.st_mtime_n         = struct.unpack(">L L", rf.read(4 *2))
        self.st_dev, self.st_ino, self.st_mode = struct.unpack(">L L L", rf.read(4 *3))
        self.st_uid, self.st_gid, self.st_size = struct.unpack(">L L L", rf.read(4 *3))

        (objid,) =  struct.unpack(">20s", rf.read(20))
        self.obj_id = binascii.b2a_hex(objid)

        (f_name_len,)   = struct.unpack(">H", rf.read(2))
        (name_and_pad,) = struct.unpack(">%ds" % f_name_len, rf.read(f_name_len))
        self.pathname   = name_and_pad.strip()

        # padding のスキップ
        pad_len = (8 - (f_name_len -2) % 8) if (f_name_len -2) % 8 != 0 else 8
        rf.read(pad_len)


    def __str__(self):
        return '%6o %s %s' % (self.st_mode, self.obj_id, self.pathname)



class GitDB(object):

    #========================================
    # オブジェクトDB の操作

    def save(self, git_obj):
        path = os.path.join('.mgit/objects', git_obj.getId())
        with open(path, "wb") as f:
            f.write(git_obj.getContents())

    def load(self, git_obj_id, git_obj):
        path = os.path.join('.mgit/objects', git_obj_id)
        with open(path, "rb") as f:
            git_obj.setId(git_obj_id)
            git_obj.setContents(f.read())

    def readObjHeader(self, git_obj_id):
        path = os.path.join('.mgit/objects', git_obj_id)

        with open(path, "r") as f:
            tmp = zlib.decompress(f.read())
            (obj_type, size) = tmp[:tmp.find('\0')].split(' ')
            return (obj_type, int(size))


    #========================================
    # リファレンス の操作

    def dereference(self, ref_name):
        '''
        reference の指し示す obj_id を取得する。
        reference のreference 対応のため、末端referenceもペアで返す
        @return (terminal_ref_name, obj_id)
        '''
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

        old_obj_id_str = old_obj_id if old_obj_id != None else '0'*40

        logfile = open(logpath, 'a')
        logfile.write( '%s %s %s\n' % (old_obj_id_str, git_obj_id,
                                       datetime.datetime.today().strftime("%Y%m%dT%H%M%S")))


    #========================================
    # インデックス の操作

        # これから作ります



