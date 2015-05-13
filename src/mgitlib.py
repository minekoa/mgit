#!/usr/bin/env python
#-*- coding: shift_jis -*-

import zlib
import hashlib
import struct
import os.path
import binascii
import re
import datetime
import time
import ConfigParser

#============================================================
#
# GitObject 
#
#============================================================

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


class GitCommit(GitObject):
    '''
    <生COMMIT>    := <ヘッダ>\0<ボディ>
    <ヘッダ>      := commit <サイズ>
    <ボディ>      := <ルートTREE>\n<親コミット>\n<AUTHOR>\n<committr>\n\n<メッセージ>
                   | <ルートTREE>\n<AUTHOR>\n<COMMITTER>\n\n<メッセージ>
    <ルートTREE>  := tree <ハッシュ文字列>
    <親コミット>  := parent <ハッシュ文字列>
    <AUTHOR>      := author <名前> \<<メアド>\> <時間>
    <COMMITTER>   := committer <名前> \<<メアド>\> <時間>
    <メッセージ>  := (任意の文字列、複数行可）

    <時間>           := (エポック秒 + タイムゾーン。例: 1401425880 +0900)
    <ファイル種別>   := (8進数文字列, 最大6桁)
    <ハッシュ文字列> := (16進数文字列, 40文字)
    '''

    def __init__(self, id=None):
        self.id            =id
        self.contents      = None
        self.root_tree     = None
        self.parent_commit = None
        self.commit_info   = None

    def setCommitInfo(self, info):     self.commit_info = info
    def setRootTree(self, tree):       self.root_tree   = tree
    def setParentCommit(self, parent): self.parent_commit = parent

    def genRawContents(self):
        tree_str   = 'tree %s\n' % self.root_tree.getId()
        if self.parent_commit != None:
            parent_str = 'parent %s\n' % self.parent_commit.getId() 
        else: 
            parent_str =''

        body = '%s%s%s' % (tree_str, parent_str,
                           self.commit_info.asString())
        hdr = 'commit %d' % len(body)
        return ''.join((hdr,'\0',body))

    def pack(self, db):
        self.root_tree.pack(db)
        raw_contents = self.genRawContents()

        self.contents = zlib.compress(raw_contents)
        self.id       = self.genId(raw_contents)

        db.save(self)


    def unpack(self, db, obj_id):
        db.load(obj_id, self)
        deco_dat = zlib.decompress(self.contents)

        # ヘッダを解析
        hdr_end_idx = deco_dat.find('\0')
        otype = deco_dat[0:4]
        size  = deco_dat[4:hdr_end_idx]
        
        # 本体
        lines = deco_dat[hdr_end_idx+1:].split('\n')
        idx = 0

        tokens = lines[idx].split(' ')
        if tokens[0] == 'tree'  : 
            tree_id = tokens[1]
            self.root_tree = GitTree()
            self.root_tree.unpack(db, tree_id)
        else:
            raise ValueError('GIT_COMMIT FORMAT ERROR (tree line)')
        idx += 1
       
        tokens = lines[idx].split(' ')
        if tokens[0] == 'parent':
            parent_id = tokens[1]
            self.parent_commit = GitCommit()
            self.parent_commit.unpack(db, parent_id)
            idx += 1

        self.commit_info = CommitInfo()
        self.commit_info.parseString(lines[idx:])


        self.id = obj_id

        #CRC-CHK                                    # for debug
        raw_contents = self.genRawContents()        # for debug
        new_id       = self.genId(raw_contents)     # for debug
        print 'old_id:', obj_id                     # for debug
        print 'new_id:', new_id                     # for debug
        print 'raw:-------------------'             # for debug
        print raw_contents                          # for debug
        print '--------------------end'             # for debug


#============================================================
#
# Entities for Git
#
#============================================================

class FileAttr(object):
    TYPE_DIR      = 0o40   # ファイル種別: ディレクトリ
    TYPE_FILE     = 0o100  # ファイル種別: ファイル
    TYPE_SLNK     = 0o120  # ファイル種別: シンボリックリンク
    EXECUTABLE_OK = 0o755  # パーミッション:   実行可能 (※ TYPE=FILEのみ指定可)
    EXECUTABLE_NG = 0o644  # パーミッション:   実行不可 (※ TYPE=FILEのみ指定可)

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

    def isFile(self):
        return self.ftype == FileAttr.TYPE_FILE

    @classmethod
    def directory(cls): return cls(FileAttr.TYPE_DIR)

    @classmethod
    def symboliclink(cls): return cls(FileAttr.TYPE_SLNK)
        


class EpochTimeTz(object):
    '''大変乱暴な UTCエポック秒 + タイムゾーン の時間型'''

    @classmethod
    def now(cls):
        '''python の datetime.now() と datetime.utcnow() の差分を利用して
        無理やりタイムゾーンもどきを作ってる。他に良い方法ないかな？
        '''
        utcdate   = datetime.datetime.utcnow()
        locdate   = datetime.datetime.now()        
        delta_sec = (locdate - utcdate).seconds

        epoch_sec  = int(time.mktime(utcdate.timetuple()))
        tz_offst_h = delta_sec / 3600 if delta_sec % 3600 == 0 else  delta_sec / 3600 + 1

        return cls(epoch_sec, tz_offst_h)

    @classmethod
    def fromString(cls, soruce):
        matobj = re.match( r"([0-9]+) \+([0-9]+)", soruce )
        epoch_sec  = int(matobj.group(1))
        tz_offst_h = int(matobj.group(2)) / 100

        return cls(epoch_sec, tz_offst_h)

    def __init__(self, epoch_sec=None, tz_offset_h=None):
        self.epoch_sec  = epoch_sec
        self.tz_offst_h = tz_offset_h

    def asString(self):
        return '%s +%04d' % (self.epoch_sec, self.tz_offst_h * 100)
    

    def asDateTimeUTC(self):
        return datetime.datetime(*time.localtime(self.epoch_sec)[:6])

    def asDateTimeLocal(self):
        return datetime.datetime(
            *time.localtime(self.epoch_sec + self.tz_offset_h * 3600)[:6])


class UserInfo(object):
    '''ユーザー情報。名前付きタプルでも問題ないが、一応クラスで'''
    def __init__(self, name, email):
        self.name  = name
        self.email = email


class CommitInfo(object):
    '''コミット時の情報
    時間、コミットした人、コミットメッセージ など
    '''
    def __init__(self):
        self.author         = None
        self.authoring_time = None

        self.committer      = None
        self.commit_time    = None
        self.commit_message = None

    def setAuthorInfo(self, userinfo, time):
        '''変更した人の情報'''
        self.author = userinfo
        self.authoring_time = time

    def setCommitInfo(self, userinfo, time, msg):
        '''コミットした人の情報
        通常は「変更した人」と同じだけれども、
        「パッチ投稿→コミッタが採用」なフローだと別になる
        '''
        self.committer      = userinfo
        self.commit_time    = time
        self.commit_message = msg


    def _makeUserActionStr(self, action_name, user, epoch_time_tz):
        return '%s %s <%s> %s' % (action_name,
                                  user.name,
                                  user.email,
                                  epoch_time_tz.asString())

    def _parseUserActionStr(self, source):
        matobj = re.match( r"(author|committer) ([^<]+)<([^>]+)> ([0-9]+ \+[0-9]+)", source)
        return (matobj.group(1),
                UserInfo(matobj.group(2).strip(), matobj.group(3)),
                EpochTimeTz.fromString(matobj.group(4)))


    def asString(self):
        '''Commitオブジェクト生成用文字列変換'''
        # author
        athr_str   = self._makeUserActionStr('author',
                                             self.author,
                                             self.authoring_time)
        # committer
        cmtr_str   = self._makeUserActionStr('committer',
                                             self.committer,
                                             self.commit_time)

        return '\n'.join( (athr_str, cmtr_str, '', self.commit_message) )

    def parseString(self, lines):
        act, user, tm = self._parseUserActionStr(lines[0])
        if act != 'author': raise ValueError()
        self.author         = user
        self.authoring_time = tm

        act, user, tm = self._parseUserActionStr(lines[1])
        if act != 'committer': raise ValueError()
        self.committer         = user
        self.commit_time = tm

        if lines[2].strip() != '': raise ValueError()

        self.commit_message = '\n'.join(lines[3:])


#============================================================
#
# Git Index
#
#============================================================

class GitIndex(object):
    def __init__(self):
        self.rows = {}

    def append(self, pathname, obj_id):
        pathname = pathname.replace(os.path.sep, '/')
        self.rows[pathname] = GitIndexRow(pathname, obj_id)

    def pack(self, wf):
        wf.write(struct.pack( ">4s L L",
                              'DISC', 2, len(self.rows)))
        for pathname, row in self.rows.items():
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
            self.rows[tmp.pathname] = tmp


        if f_cnt != len(self.rows):
            print "ERROR ! unpack failed %d != %d" % (f_cnt, len(self.rows))

    def __str__(self):
        return '\n'.join(item.__str__() for key,item in self.rows.items())


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
        self.st_ctime   = int(statinfo.st_ctime)
        self.st_ctime_n = int((statinfo.st_ctime - self.st_ctime) * 1000 * 1000 * 1000)
        self.st_mtime   = int(statinfo.st_mtime)
        self.st_mtime_n = int((statinfo.st_mtime - self.st_mtime) * 1000 * 1000 * 1000)
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


#============================================================
#
# Git DB
#
#============================================================

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

    def openIndexFile(self, mode):
        '''mode は "rb" or "wb"'''
        return open( '.mgit/index', mode )


#============================================================
#
# Git Config
#
#============================================================

class GitConfig(object):
    '''
    コンフィグファイルの読み出しを行う
    '''
    def __init__(self, inifile_path=None):
        if inifile_path == None:
            home = os.environ['HOME']
            inifile_path = os.path.join(home, '.mgitconfig')

        with open(inifile_path, 'r') as f:
            ini_parser = ConfigParser.SafeConfigParser()
            ini_parser.readfp(f)

            # User情報の初期化 ← inifile
            self.user = UserInfo(ini_parser.get('user', 'name'),
                                 ini_parser.get('user', 'email'))

        print 'load config "%s"'  % inifile_path  # for debug
        print ' user.name = %s'   % self.user.name  # for debug
        print ' user.email= <%s>' % self.user.email # for debug

    def getUserInfo(self): return self.user

