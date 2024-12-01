# -*- coding: utf-8 -*-

from boltons.tableutils import Table


def test_table_lists():
    data_lists = [['id', 'name'],
                  [1, 'John Doe'],
                  [2, 'Dale Simmons']]
    t1 = Table(data_lists)
    assert set(t1.headers) == set(['id', 'name'])
    assert len(t1) == 2
    assert 'John Doe' in repr(t1)

T2_REF_HTML = """<table>
<tr><th>id</th><td>1</td></tr>
<tr><th>name</th><td>John Doe</td></tr>
</table>"""

T3_REF_HTML = """<table>
<thead>
<tr><th>id</th><th>name</th></tr>
</thead>
<tbody>
<tr><td>1</td><td>John Doe</td></tr>
<tr><td>2</td><td>Dale Simmons</td></tr>
<tr><td>3</td><td>Kurt Rose</td></tr>
<tr><td>4</td><td>None</td></tr>
</tbody>
</table>"""


def test_table_dicts():
    data_dicts = [{'id': 1, 'name': 'John Doe'},
                  {'id': 2, 'name': 'Dale Simmons'}]
    t2 = Table.from_dict(data_dicts[0])
    t3 = Table.from_dict(data_dicts)
    t3.extend([[3, 'Kurt Rose'], [4]])

    assert set(t2.headers) == set(['id', 'name'])
    assert len(t2) == 1
    # the sorted() stuff handles ordering differences between versions
    # TODO: should maybe change Table to sort the headers of dicts and such?
    assert sorted(t2.to_html()) == sorted(T2_REF_HTML)
    assert sorted(t3.to_html()) == sorted(T3_REF_HTML)
    assert t3.to_text()


def test_table_obj():
    class TestType(object):
        def __init__(self):
            self.greeting = 'hi'

    t4 = Table.from_object(TestType())
    assert len(t4) == 1
    assert 'greeting' in t4.headers
