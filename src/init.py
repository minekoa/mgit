#!/usr/bin/env python
#-*- coding:shift_jis -*-
import os.path

if __name__ == '__main__':

    # �f�B���N�g���̍쐬
    path_list = ['.mgit/objects',
                 '.mgit/refs',
                 '.mgit/refs/heads',
                 '.mgit/logs'
                 ]
                 
    for path in path_list:
        if not os.path.exists(path): os.makedirs(path)


    # �K�{�t�@�C���̍쐬
    if not os.path.exists('.mgit/HEAD'):
        f = open('.mgit/HEAD', 'w')
        f.write('ref: refs/heads/master');


