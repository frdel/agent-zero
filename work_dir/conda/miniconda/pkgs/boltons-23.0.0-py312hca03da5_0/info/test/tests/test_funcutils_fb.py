import pytest
from boltons.funcutils import wraps, FunctionBuilder


def pita_wrap(flag=False):

    def cedar_dec(func):
        @wraps(func)
        def cedar_wrapper(*a, **kw):
            return (flag, func.__name__, func(*a, **kw))
        return cedar_wrapper

    return cedar_dec


def wrappable_func(a, b):
    return a, b


def wrappable_varkw_func(a, b, **kw):
    return a, b


def test_wraps_basic():

    @pita_wrap(flag=True)
    def simple_func():
        '''"""a tricky docstring"""'''
        return 'hello'

    assert simple_func() == (True, 'simple_func', 'hello')
    assert simple_func.__doc__ == '''"""a tricky docstring"""'''

    assert callable(simple_func.__wrapped__)
    assert simple_func.__wrapped__() == 'hello'
    assert simple_func.__wrapped__.__doc__ == '''"""a tricky docstring"""'''

    @pita_wrap(flag=False)
    def less_simple_func(arg='hello'):
        return arg

    assert less_simple_func() == (False, 'less_simple_func', 'hello')
    assert less_simple_func(arg='bye') == (False, 'less_simple_func', 'bye')

    with pytest.raises(TypeError):
        simple_func(no_such_arg='nope')

    @pita_wrap(flag=False)
    def default_non_roundtrippable_repr(x=lambda y: y + 1):
        return x(1)

    assert default_non_roundtrippable_repr() == (
        False, 'default_non_roundtrippable_repr', 2)


def test_wraps_injected():
    def inject_string(func):
        @wraps(func, injected="a")
        def wrapped(*args, **kwargs):
            return func(1, *args, **kwargs)
        return wrapped

    assert inject_string(wrappable_func)(2) == (1, 2)

    def inject_list(func):
        @wraps(func, injected=["b"])
        def wrapped(a, *args, **kwargs):
            return func(a, 2, *args, **kwargs)
        return wrapped

    assert inject_list(wrappable_func)(1) == (1, 2)

    def inject_nonexistent_arg(func):
        @wraps(func, injected=["X"])
        def wrapped(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapped

    with pytest.raises(ValueError):
        inject_nonexistent_arg(wrappable_func)

    def inject_missing_argument(func):
        @wraps(func, injected="c")
        def wrapped(*args, **kwargs):
            return func(1, *args, **kwargs)
        return wrapped

    def inject_misc_argument(func):
        # inject_to_varkw is default True, just being explicit
        @wraps(func, injected="c", inject_to_varkw=True)
        def wrapped(*args, **kwargs):
            return func(c=1, *args, **kwargs)
        return wrapped

    assert inject_misc_argument(wrappable_varkw_func)(1, 2) == (1, 2)

    def inject_misc_argument_no_varkw(func):
        @wraps(func, injected="c", inject_to_varkw=False)
        def wrapped(*args, **kwargs):
            return func(c=1, *args, **kwargs)
        return wrapped

    with pytest.raises(ValueError):
        inject_misc_argument_no_varkw(wrappable_varkw_func)


def test_wraps_update_dict():

    def updated_dict(func):
        @wraps(func, update_dict=True)
        def wrapped(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapped

    def f(a, b):
        return a, b

    f.something = True

    assert getattr(updated_dict(f), 'something')


def test_wraps_unknown_args():

    def fails(func):
        @wraps(func, foo="bar")
        def wrapped(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapped

    with pytest.raises(TypeError):
        fails(wrappable_func)


def test_FunctionBuilder_invalid_args():
    with pytest.raises(TypeError):
        FunctionBuilder(name="fails", foo="bar")


def test_FunctionBuilder_invalid_body():
    with pytest.raises(SyntaxError):
        FunctionBuilder(name="fails", body="*").get_func()


def test_FunctionBuilder_modify():
    fb = FunctionBuilder('return_five', doc='returns the integer 5',
                         body='return 5')
    f = fb.get_func()
    assert f() == 5

    fb.varkw = 'kw'
    f_kw = fb.get_func()
    assert f_kw(ignored_arg='ignored_val') == 5


def test_wraps_wrappers():
    call_list = []

    def call_list_appender(func):
        @wraps(func)
        def appender(*a, **kw):
            call_list.append((a, kw))
            return func(*a, **kw)
        return appender

    with pytest.raises(TypeError):
        class Num(object):
            def __init__(self, num):
                self.num = num

            @call_list_appender
            @classmethod
            def added(cls, x, y=1):
                return cls(x + y)

    return


def test_FunctionBuilder_add_arg():
    fb = FunctionBuilder('return_five', doc='returns the integer 5',
                         body='return 5')
    f = fb.get_func()
    assert f() == 5

    fb.add_arg('val')
    f = fb.get_func()
    assert f(val='ignored') == 5

    with pytest.raises(ValueError) as excinfo:
        fb.add_arg('val')
    excinfo.typename == 'ExistingArgument'

    fb = FunctionBuilder('return_val', doc='returns the value',
                         body='return val')

    broken_func = fb.get_func()
    with pytest.raises(NameError):
        broken_func()

    fb.add_arg('val', default='default_val')

    better_func = fb.get_func()
    assert better_func() == 'default_val'

    assert better_func('positional') == 'positional'
    assert better_func(val='keyword') == 'keyword'


def test_wraps_expected():
    def expect_string(func):
        @wraps(func, expected="c")
        def wrapped(*args, **kwargs):
            args, c = args[:2], args[-1]
            return func(*args, **kwargs) + (c,)
        return wrapped

    expected_string = expect_string(wrappable_func)
    assert expected_string(1, 2, 3) == (1, 2, 3)

    with pytest.raises(TypeError) as excinfo:
        expected_string(1, 2)

    # a rough way of making sure we got the kind of error we expected
    assert 'argument' in repr(excinfo.value)

    def expect_list(func):
        @wraps(func, expected=["c"])
        def wrapped(*args, **kwargs):
            args, c = args[:2], args[-1]
            return func(*args, **kwargs) + (c,)
        return wrapped

    assert expect_list(wrappable_func)(1, 2, c=4) == (1, 2, 4)

    def expect_pair(func):
        @wraps(func, expected=[('c', 5)])
        def wrapped(*args, **kwargs):
            args, c = args[:2], args[-1]
            return func(*args, **kwargs) + (c,)
        return wrapped

    assert expect_pair(wrappable_func)(1, 2) == (1, 2, 5)

    def expect_dict(func):
        @wraps(func, expected={'c': 6})
        def wrapped(*args, **kwargs):
            args, c = args[:2], args[-1]
            return func(*args, **kwargs) + (c,)
        return wrapped

    assert expect_dict(wrappable_func)(1, 2) == (1, 2, 6)


def test_defaults_dict():
    def example(req, test='default'):
        return req

    fb_example = FunctionBuilder.from_func(example)
    assert 'test' in fb_example.args
    dd = fb_example.get_defaults_dict()
    assert dd['test'] == 'default'
    assert 'req' not in dd


def test_get_arg_names():
    def example(req, test='default'):
        return req

    fb_example = FunctionBuilder.from_func(example)
    assert 'test' in fb_example.args
    assert fb_example.get_arg_names() == ('req', 'test')
    assert fb_example.get_arg_names(only_required=True) == ('req',)


@pytest.mark.parametrize(
    "args, varargs, varkw, defaults, invocation_str, sig_str",
    [
        (["a", "b"], None, None, None, "a, b", "(a, b)"),
        (None, "args", "kwargs", None, "*args, **kwargs", "(*args, **kwargs)"),
        ("a", None, None, dict(a="a"), "a", "(a)"),
    ],
)
def test_get_invocation_sig_str(
    args, varargs, varkw, defaults, invocation_str, sig_str
):
    fb = FunctionBuilder(
        name='return_five',
        body='return 5',
        args=args,
        varargs=varargs,
        varkw=varkw,
        defaults=defaults
    )

    assert fb.get_invocation_str() == invocation_str
    assert fb.get_sig_str() == sig_str
