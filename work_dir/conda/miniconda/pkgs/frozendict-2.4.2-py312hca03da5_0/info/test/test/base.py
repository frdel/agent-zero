import pytest


class FrozendictTestBase:
    _FrozendictClass = None
    
    @property
    def FrozendictClass(self):
        val = self._FrozendictClass
        
        if val is None:
            raise ValueError("FrozendictClass is None")
        
        return val
    
    @FrozendictClass.setter
    def FrozendictClass(self, val):
        self._FrozendictClass = val
    
    _c_ext = None
    
    @property
    def c_ext(self):
        val = self._c_ext
        
        if val is None:
            raise ValueError("c_ext is None")
        
        return val
    
    @c_ext.setter
    def c_ext(self, val):
        self._c_ext = val
    
    _is_subclass = None
    
    @property
    def is_subclass(self):
        val = self._is_subclass
        
        if val is None:
            raise ValueError("is_subclass is None")
        
        return val
    
    @is_subclass.setter
    def is_subclass(self, val):
        self._is_subclass = val
    
    ####################################################################
    # dict fixtures

    @pytest.fixture
    def fd_dict(self):
        return {
            "Guzzanti": "Corrado", 
            "Hicks": "Bill", 
            self.FrozendictClass({1: 2}): "frozen"
        }

    @pytest.fixture
    def fd_dict_hole(self, fd_dict):
        new_dict = fd_dict.copy()
        del new_dict["Guzzanti"]
        return new_dict

    @pytest.fixture
    def fd_dict_eq(self):
        return {
            "Hicks": "Bill", 
            "Guzzanti": "Corrado", 
            self.FrozendictClass({1: 2}): "frozen"
        }

    @pytest.fixture
    def fd_dict_2(self):
        return {
            "Guzzanti": "Corrado", 
            "Hicks": "Bill", 
            "frozen": self.FrozendictClass({1: 2})
        }

    @pytest.fixture
    def fd_dict_sabina(self):
        return {'Corrado': 'Guzzanti', 'Sabina': 'Guzzanti'}

    @pytest.fixture
    def generator_seq2(self, fd_dict):
        seq2 = list(fd_dict.items())
        seq2.append(("Guzzanti", "Mario"))
        return (x for x in seq2)

    ####################################################################
    # frozendict fixtures

    @pytest.fixture
    def fd(self, fd_dict):
        return self.FrozendictClass(fd_dict)

    @pytest.fixture
    def fd_hole(self, fd_dict_hole):
        return self.FrozendictClass(fd_dict_hole)

    @pytest.fixture
    def fd_unhashable(self):
        return self.FrozendictClass({1: []})

    @pytest.fixture
    def fd_eq(self, fd_dict_eq):
        return self.FrozendictClass(fd_dict_eq)
    
    @pytest.fixture
    def fd2(self, fd_dict_2):
        return self.FrozendictClass(fd_dict_2)

    @pytest.fixture
    def fd_sabina(self, fd_dict_sabina):
        return self.FrozendictClass(fd_dict_sabina)

    @pytest.fixture
    def fd_items(self, fd_dict):
        return tuple(fd_dict.items())

    @pytest.fixture
    def fd_empty(self):
        return self.FrozendictClass()

    @pytest.fixture
    def module_prefix(self):
        if self.is_subclass:
            return ""
        
        return "frozendict."
    
