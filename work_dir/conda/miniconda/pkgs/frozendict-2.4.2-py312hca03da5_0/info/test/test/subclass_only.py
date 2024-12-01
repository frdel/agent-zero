from copy import copy, deepcopy
from .base import FrozendictTestBase


class FrozendictSubclassOnlyTest(FrozendictTestBase):
    _FrozendictMissingClass = None
    
    @property
    def FrozendictMissingClass(self):
        val = self._FrozendictMissingClass
        
        if val is None:
            raise ValueError("FrozendictMissingClass is None")
        
        return val
    
    @FrozendictMissingClass.setter
    def FrozendictMissingClass(self, val):
        self._FrozendictMissingClass = val
    
    ####################################################################
    # tests
    
    def test_empty_sub(self, fd_empty):
        fd_empty_2 = self.FrozendictClass({})
        fd_empty_3 = self.FrozendictClass([])
        fd_empty_4 = self.FrozendictClass({}, **{})
        
        assert fd_empty == fd_empty_2 == fd_empty_3 == fd_empty_4
        assert fd_empty is not fd_empty_2 is not fd_empty_3
        assert fd_empty is not fd_empty_4
    
    def test_constructor_self_sub(self, fd):
        fd_clone = self.FrozendictClass(fd)
        assert fd == fd_clone
        assert fd is not fd_clone

    def test_copy_sub(self, fd):
        fd_copy = fd.copy()
        assert fd_copy == fd
        assert fd_copy is not fd

    def test_copycopy_sub(self, fd, fd_unhashable):
        fd_copy = copy(fd)
        fd_copy_unhashable = copy(fd_unhashable)
        assert fd_copy == fd
        assert fd_copy_unhashable == fd_unhashable
        assert fd_copy is not fd
        assert fd_copy_unhashable is not fd_unhashable

    def test_deepcopy_sub(self, fd):
        fd_copy = deepcopy(fd)
        assert fd_copy == fd
        assert fd_copy is not fd

    def test_init_sub(self, fd):
        fd_copy = fd.copy()
        fd_clone = self.FrozendictClass(dict(fd))
        fd.__init__({"Trump": "Donald"})
        assert fd_copy == fd
        assert fd_clone == fd
        assert fd_copy is not fd

    def test_del_empty_sub(self, fd_empty):
        f = self.FrozendictClass({1: 2})
        f2 = f.delete(1)
        assert f2 == fd_empty
        assert f2 is not fd_empty

    def test_missing(self, fd):
        fd_missing = self.FrozendictMissingClass(fd)
        assert fd_missing[0] == 0
