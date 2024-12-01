
from boltons.tbutils import ParsedException


def test_parsed_exc_basic():
    _tb_str = u"""\
Traceback (most recent call last):
  File "example.py", line 2, in <module>
    plarp
NameError: name 'plarp' is not defined"""

    parsed_tb = ParsedException.from_string(_tb_str)
    print(parsed_tb)
    assert parsed_tb.exc_type == 'NameError'
    assert parsed_tb.exc_msg == "name 'plarp' is not defined"
    assert parsed_tb.frames == [{'source_line': u'plarp',
                                 'filepath': u'example.py',
                                 'lineno': u'2',
                                 'funcname': u'<module>'}]

    assert parsed_tb.to_string() == _tb_str


def test_parsed_exc_nosrcline():
    """just making sure that everything can be parsed even if there is
    a line without source and also if the exception has no message"""

    _tb_str = u"""\
Traceback (most recent call last):
  File "/home/mahmoud/virtualenvs/chert/bin/chert", line 9, in <module>
    load_entry_point('chert==0.2.1.dev0', 'console_scripts', 'chert')()
  File "/home/mahmoud/projects/chert/chert/core.py", line 1281, in main
    ch.process()
  File "/home/mahmoud/projects/chert/chert/core.py", line 741, in process
    self.load()
  File "<boltons.FunctionBuilder-0>", line 2, in load
  File "/home/mahmoud/projects/lithoxyl/lithoxyl/logger.py", line 291, in logged_func
    return func_to_log(*a, **kw)
  File "/home/mahmoud/projects/chert/chert/core.py", line 775, in load
    raise RuntimeError
RuntimeError"""

    parsed_tb = ParsedException.from_string(_tb_str)

    assert parsed_tb.exc_type == 'RuntimeError'
    assert parsed_tb.exc_msg == ''

    assert len(parsed_tb.frames) == 6
    assert parsed_tb.frames[3] == {'source_line': u'',
                                   'filepath': u'<boltons.FunctionBuilder-0>',
                                   'lineno': u'2',
                                   'funcname': u'load'}
    assert parsed_tb.to_string() == _tb_str
