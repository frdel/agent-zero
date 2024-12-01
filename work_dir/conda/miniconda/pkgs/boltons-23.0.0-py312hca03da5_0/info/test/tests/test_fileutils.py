# -*- coding: utf-8 -*-

from boltons.fileutils import FilePerms


def test_fileperms():
    up = FilePerms()
    up.other = ''
    up.user = 'xrw'
    up.group = 'rrrwx'
    try:
        up.other = 'nope'
    except ValueError:
        # correctly raised ValueError on invalid chars
        pass

    assert repr(up) == "FilePerms(user='rwx', group='rwx', other='')"
    assert up.user == 'rwx'
    assert oct(int(up)).endswith('770')  # 0770 on py2 and 0o770 on py3

    assert int(FilePerms()) == 0
