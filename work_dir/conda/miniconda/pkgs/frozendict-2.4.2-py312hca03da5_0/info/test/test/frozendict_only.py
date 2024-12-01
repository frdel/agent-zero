import io
import pickle
import pytest
from copy import copy, deepcopy
from .base import FrozendictTestBase


class FrozendictOnlyTest(FrozendictTestBase):
    def test_empty(self, fd_empty):
        fd_empty_set = self.FrozendictClass({})
        fd_empty_list = self.FrozendictClass([])
        fd_empty_dict = self.FrozendictClass({}, **{})
        
        assert fd_empty is fd_empty_set is fd_empty_list
        assert fd_empty is fd_empty_dict

    def test_constructor_self_1(self, fd):
        assert fd is self.FrozendictClass(fd)

    def test_vars(self, fd):
        with pytest.raises(TypeError):
            vars(fd)

    def test_setattr(self, fd):
        with pytest.raises(AttributeError):
            fd._initialized = False

    def test_copy(self, fd):
        assert fd.copy() is fd

    def test_copycopy(self, fd, fd_unhashable):
        assert copy(fd) is fd
        assert copy(fd_unhashable) is fd_unhashable

    def test_deepcopy(self, fd):
        assert deepcopy(fd) is fd

    def test_init(self, fd):
        fd_copy = fd.copy()
        fd_clone = self.FrozendictClass(dict(fd))
        fd.__init__({"Trump": "Donald"})
        assert fd_copy is fd
        assert fd_clone == fd

    def test_del_empty(self):
        f = self.FrozendictClass({1: 2})
        assert f.delete(1) is self.FrozendictClass()

    def test_pickle_core(self, fd):
        class CustomUnpickler(pickle.Unpickler):
            def find_class(self, module, name):
                assert module == 'frozendict'
                assert name == 'frozendict'
                return super().find_class('frozendict.core', name)

        dump = pickle.dumps(fd)
        assert dump
        assert CustomUnpickler(io.BytesIO(dump)).load() == fd
