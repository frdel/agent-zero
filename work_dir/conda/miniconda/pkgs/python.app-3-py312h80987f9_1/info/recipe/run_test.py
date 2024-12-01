import sys
from subprocess import check_call

print('-----')
x = sys.prefix + '/python.app/Contents/MacOS/python'
check_call([x, '-V'])
check_call([x, '-c', 'import sys; print(sys.prefix)'])

if sys.version_info[:2] >= (2, 7):
    from subprocess import check_output

    out = check_output([sys.prefix + '/bin/pythonw', 't.py', '1 2', '3'])
    print(out)
    assert eval(out.decode()) == ['t.py', '1 2', '3'], out
