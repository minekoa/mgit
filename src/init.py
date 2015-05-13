#!/usr/bin/env python
#-*- coding:shift_jis -*-
import os.path

if __name__ == '__main__':

    # ディレクトリの作成
    path_list = ['.mgit/objects',
                 '.mgit/refs',
                 '.mgit/refs/heads',
                 '.mgit/logs'
                 ]
                 
    for path in path_list:
        if not os.path.exists(path): os.makedirs(path)


    # 必須ファイルの作成
    if not os.path.exists('.mgit/HEAD'):
        f = open('.mgit/HEAD', 'w')
        f.write('ref: refs/heads/master');


