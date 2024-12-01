# -*- coding: utf-8 -*-
import json
import sys

try:
    from cStringIO import StringIO
except:
    from io import StringIO

from boltons.tbutils import (TracebackInfo,
                             ExceptionInfo,
                             print_exception,
                             fix_print_exception,
                             ContextualCallpoint,
                             ContextualExceptionInfo)



def test_exception_info():
    # test ExceptionInfo and TracebackInfo and hooks, via StringIOs
    builtin_exc_hook = sys.excepthook
    fix_print_exception()
    tbi_str = ''

    def test():
        raise ValueError('yay fun')

    fake_stderr1 = StringIO()
    fake_stderr2 = StringIO()
    sys.stderr = fake_stderr1

    try:
        test()
    except:
        _, _, exc_traceback = sys.exc_info()
        tbi = TracebackInfo.from_traceback(exc_traceback)
        exc_info = ExceptionInfo.from_exc_info(*sys.exc_info())
        exc_info2 = ExceptionInfo.from_current()
        tbi_str = str(tbi)
        print_exception(*sys.exc_info(), file=fake_stderr2)
        new_exc_hook_res = fake_stderr2.getvalue()
        builtin_exc_hook(*sys.exc_info())
        builtin_exc_hook_res = fake_stderr1.getvalue()
    finally:
        sys.stderr = sys.__stderr__

    # Single frame
    single_frame_str = tbi.frames[-1].tb_frame_str()
    assert 'in test' in single_frame_str
    assert 'yay fun' in single_frame_str

    # Traceback info
    assert len(tbi_str.splitlines()) == 5
    assert 'yay fun' in tbi_str

    # Full except hook output
    assert 'ValueError: yay fun' in new_exc_hook_res
    assert "ValueError('yay fun')" in new_exc_hook_res
    assert len(new_exc_hook_res) > len(tbi_str)

    assert new_exc_hook_res == builtin_exc_hook_res


def test_contextual():
    def func1():
        return func2()
    def func2():
        x = 5
        return func3()
    def func3():
        return ContextualCallpoint.from_current(level=2)

    callpoint = func1()
    assert callpoint.func_name == 'func2'
    line = str(callpoint.line)
    assert line.startswith(' ')
    assert line.strip() == 'return func3()'
    assert 'func2' in repr(callpoint)

    try:
        json.dumps(callpoint.to_dict())
    except TypeError:
        raise AssertionError("to_dict result is not JSON serializable")

    def func_a():
        a = 1
        raise Exception('func_a exception')
    def func_b():
        b = 2
        return func_a()
    def func_c():
        c = 3
        return func_b()

    try:
        func_c()
    except Exception as e:
        ctx_ei = ContextualExceptionInfo.from_current()
        ctx_ei_str = ctx_ei.get_formatted()

    ctx_ei_lines = ctx_ei_str.splitlines()
    assert ctx_ei_lines[-1] == 'Exception: func_a exception'
    assert ctx_ei_lines[0] == 'Traceback (most recent call last):'
    assert len(ctx_ei_lines) == 10
    assert "Exception('func_a exception')" in ctx_ei_str
    assert ctx_ei.tb_info.frames[2].local_reprs['b'] == '2'
