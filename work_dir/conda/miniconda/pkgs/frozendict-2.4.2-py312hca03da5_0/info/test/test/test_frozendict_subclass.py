from .common import FrozendictCommonTest
from .subclass_only import FrozendictSubclassOnlyTest
import frozendict as cool
from frozendict import frozendict as FrozendictClass


is_subclass = True


class FrozendictSubclass(FrozendictClass):
    def __new__(cls, *args, **kwargs):
        return super().__new__(cls, *args, **kwargs)


class FrozendictMissingSubclass(FrozendictClass):
    def __new__(cls, *args, **kwargs):
        return super().__new__(cls, *args, **kwargs)
    
    def __missing__(self, key):
        return key


class TestFrozendictSubclass(
        FrozendictCommonTest, 
        FrozendictSubclassOnlyTest
):
    FrozendictClass = FrozendictSubclass
    FrozendictMissingClass = FrozendictMissingSubclass
    c_ext = cool.c_ext
    is_subclass = is_subclass
