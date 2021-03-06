  # -*- coding: utf-8 -*-
'''
Test Vincent.vega
-----------------

'''
from datetime import datetime, timedelta
from itertools import product
import time
import json

from vincent.vega import (KeyedList, ValidationError, GrammarDict, grammar,
                          GrammarClass, Visualization, Data, LoadError,
                          ValueRef, Mark, PropertySet, Scale, Axis,
                          MarkProperties, MarkRef, DataRef, Scale,
                          AxisProperties, Axis)
import nose.tools as nt

import pandas as pd
import numpy as np


sequences = {
    'int': range,
    'float': lambda l: map(float, range(l)),
    'char': lambda l: map(chr, range(97, 97 + l)),
    'datetime': lambda l: [datetime.now() + timedelta(days=i)
                           for i in xrange(l)],
    'Timestamp': lambda l: pd.date_range('1/2/2000', periods=l),
    'numpy float': lambda l: map(np.float32, range(l)),
    'numpy int': lambda l: map(np.int32, range(l))}


def test_keyed_list():
    """Test keyed list implementation"""

    class TestKey(object):
        """Test object for Keyed List"""
        def __init__(self, name=None):
            self.name = name

    key_list = KeyedList(attr_name='name')

    #Basic usage
    test_key = TestKey(name='test')
    key_list.append(test_key)
    nt.assert_equal(test_key, key_list['test'])

    #Bad key
    with nt.assert_raises(KeyError) as err:
        key_list['test_1']
    nt.assert_equal(err.exception.message, ' "test_1" is an invalid key')

    #Repeated keys
    test_key_1 = TestKey(name='test')
    key_list.append(test_key_1)
    with nt.assert_raises(ValidationError) as err:
        key_list['test']
    nt.assert_equal(err.expected, ValidationError)
    nt.assert_equal(err.exception.message, 'duplicate keys found')

    #Setting keys
    key_list.pop(-1)
    test_key_2 = TestKey(name='test_2')
    key_list['test_2'] = test_key_2
    nt.assert_equal(key_list['test_2'], test_key_2)

    mirror_key_2 = TestKey(name='test_2')
    key_list['test_2'] = mirror_key_2
    nt.assert_equal(key_list['test_2'], mirror_key_2)

    #Keysetting errors
    test_key_3 = TestKey(name='test_3')
    with nt.assert_raises(ValidationError) as err:
        key_list['test_4'] = test_key_3
    nt.assert_equal(err.expected, ValidationError)
    nt.assert_equal(err.exception.message,
                    "key must be equal to 'name' attribute")

    key_list = KeyedList(attr_name='type')
    test_key_4 = TestKey(name='test_key_4')
    with nt.assert_raises(ValidationError) as err:
        key_list['test_key_4'] = test_key_4
    nt.assert_equal(err.expected, ValidationError)
    nt.assert_equal(err.exception.message, 'object must have type attribute')


def test_grammar():
    """Grammar decorator behaves correctly."""

    validator_fail = False

    class DummyType(object):
        pass

    class TestGrammarClass(object):
        def __init__(self):
            self.grammar = GrammarDict()

        @grammar
        def test_grammar(value):
            if validator_fail:
                raise ValueError('validator failed')

        @grammar(grammar_type=DummyType)
        def test_grammar_with_type(value):
            if validator_fail:
                raise ValueError('validator failed')

        @grammar(grammar_name='a name')
        def test_grammar_with_name(value):
            if validator_fail:
                raise ValueError('validator failed')

    test = TestGrammarClass()
    nt.assert_is_none(test.test_grammar)
    nt.assert_dict_equal(test.grammar, {})

    test.test_grammar = 'testing'
    nt.assert_equal(test.test_grammar, 'testing')
    nt.assert_dict_equal(test.grammar, {'test_grammar': 'testing'})

    del test.test_grammar
    nt.assert_is_none(test.test_grammar)
    nt.assert_dict_equal(test.grammar, {})

    validator_fail = True
    nt.assert_raises_regexp(ValueError, 'validator failed', setattr, test,
                            'test_grammar', 'testing')

    # grammar with type checking
    test = TestGrammarClass()
    validator_fail = False
    dummy = DummyType()
    test.test_grammar_with_type = dummy
    nt.assert_equal(test.test_grammar_with_type, dummy)
    nt.assert_dict_equal(test.grammar, {'test_grammar_with_type': dummy})
    nt.assert_raises_regexp(ValueError, 'must be DummyType', setattr, test,
                            'test_grammar_with_type', 'testing')
    validator_fail = True
    nt.assert_raises_regexp(ValueError, 'validator failed', setattr, test,
                            'test_grammar_with_type', dummy)

    # grammar with field name
    test = TestGrammarClass()
    validator_fail = False
    test.test_grammar_with_name = 'testing'
    nt.assert_equal(test.test_grammar_with_name, 'testing')
    nt.assert_dict_equal(test.grammar, {'a name': 'testing'})
    validator_fail = True
    nt.assert_raises_regexp(ValueError, 'validator failed', setattr, test,
                            'test_grammar_with_name', 'testing')


def test_grammar_dict():
    """Test Vincent Grammar Dict"""

    g_dict = GrammarDict()
    test = Visualization()
    test_dict = {'axes': [], 'data': [], 'marks': [], 'scales': []}
    test_str = '{"marks": [], "axes": [], "data": [], "scales": []}'

    nt.assert_equal(test.grammar(), test_dict)
    nt.assert_equal(str(test.grammar), test_str)
    nt.assert_equal(g_dict.encoder(test), test.grammar)


def assert_grammar_typechecking(grammar_types, test_obj):
    """Assert that the grammar fields of a test object are correctly type-checked.

    `grammar_types` should be a list of (name, type) pairs, and `test_obj`
    should be an instance of the object to test.
    """
    class BadType(object):
        pass

    for name, objects in grammar_types:
        for obj in objects:
            tmp_obj = obj()
            setattr(test_obj, name, tmp_obj)
            nt.assert_equal(getattr(test_obj, name), tmp_obj)
            bad_obj = BadType()
            nt.assert_raises_regexp(ValueError, name + '.*' + obj.__name__,
                                    setattr, test_obj, name, bad_obj)
            nt.assert_equal(getattr(test_obj, name), tmp_obj)


def assert_manual_typechecking(bad_grammar, test_obj):
    """Some attrs use the _assert_is_type func for typechecking"""

    for attr, value in bad_grammar:
        with nt.assert_raises(ValueError) as err:
            setattr(test_obj, attr, value)

        nt.assert_equal(err.expected, ValueError)


def assert_grammar_validation(grammar_errors, test_obj):
    """Check grammar methods for validation errors"""

    for attr, value, error, message in grammar_errors:
        with nt.assert_raises(error) as err:
            setattr(test_obj, attr, value)

        nt.assert_equal(err.exception.message, message)


class TestGrammarClass(object):
    """Test GrammarClass's built-in methods that aren't tested elsewhere"""

    def test_bad_init(self):
        """Test bad initialization"""
        nt.assert_raises(ValueError, GrammarClass, width=50)

    def test_validation(self):
        """Test validation of grammar"""
        test = Visualization()
        test.axes.append({'bad axes': 'ShouldRaiseError'})
        with nt.assert_raises(ValidationError) as err:
            test.validate()
        nt.assert_equal(err.exception.message,
                        'invalid contents: axes[0] must be Axis')


class TestVisualization(object):
    """Test the Visualization Class"""

    def test_grammar_typechecking(self):
        """Visualization fields are correctly type checked"""

        grammar_types = [('name', [str]),
                         ('width', [int]),
                         ('height', [int]),
                         ('data', [list, KeyedList]),
                         ('scales', [list, KeyedList]),
                         ('axes', [list, KeyedList]),
                         ('marks', [list, KeyedList])]

        assert_grammar_typechecking(grammar_types, Visualization())

    def test_validation_checking(self):
        """Visualization fields are grammar-checked"""

        grammar_errors = [('width', -1, ValueError,
                           'width cannot be negative'),
                          ('height', -1, ValueError,
                           'height cannot be negative'),
                          ('viewport', [1], ValueError,
                           'viewport must have 2 dimensions'),
                          ('viewport', [-1, -1], ValueError,
                           'viewport dimensions cannot be negative'),
                          ('padding', {'top': 2}, ValueError,
                           ('Padding must have keys "top", "left", "right",'
                            ' "bottom".')),
                          ('padding',
                           {'top': 1, 'left': 1, 'right': 1, 'bottom': -1},
                           ValueError, 'Padding cannot be negative.'),
                          ('padding', -1, ValueError,
                           'Padding cannot be negative.')]

        assert_grammar_validation(grammar_errors, Visualization())

    def test_manual_typecheck(self):
        """Test manual typechecking for elements like marks"""

        test_attr = [('data', [1]), ('scales', [1]),
                     ('axes', [1]), ('marks', [1])]

        assert_manual_typechecking(test_attr, Visualization())

    def test_validation(self):
        """Test Visualization validation"""

        test_obj = Visualization()
        with nt.assert_raises(ValidationError) as err:
            test_obj.validate()
        nt.assert_equal(err.exception.message,
                        'data must be defined for valid visualization')

        test_obj.data = [Data(name='test'), Data(name='test')]
        with nt.assert_raises(ValidationError) as err:
            test_obj.validate()
        nt.assert_equal(err.exception.message,
                        'data has duplicate names')

    def test_to_json(self):
        """Test JSON to string"""

        pretty = '''{
          "marks": [],
          "axes": [],
          "data": [],
          "scales": []
        }'''

        test = Visualization()
        actual, tested = json.loads(pretty), json.loads(test.to_json())
        nt.assert_dict_equal(actual, tested)


class TestData(object):
    """Test the Data class"""

    def test_grammar_typechecking(self):
        """Data fields are correctly type-checked"""
        grammar_types = [
            ('name', [str]),
            ('url', [str]),
            ('values', [list]),
            ('source', [str]),
            ('transform', [list])]

        assert_grammar_typechecking(grammar_types, Data('name'))

    def test_validate(self):
        """Test Data name validation"""
        test_obj = Data()
        del test_obj.name
        nt.assert_raises(ValidationError, test_obj.validate)

    def test_serialize(self):
        """Objects are serialized to JSON-compatible objects"""

        def epoch(obj):
            """Convert to JS Epoch time"""
            return int(time.mktime(obj.timetuple())) * 1000

        types = [('test', str, 'test'),
                 (pd.Timestamp('2013-06-08'), int,
                  epoch(pd.Timestamp('2013-06-08'))),
                 (datetime.utcnow(), int, epoch(datetime.utcnow())),
                 (1, int, 1),
                 (1.0, float, 1.0),
                 (np.float32(1), float, 1.0),
                 (np.int32(1), int, 1),
                 (np.float64(1), float, 1.0),
                 (np.int64(1), int, 1)]

        for puts, pytype, gets in types:
            nt.assert_equal(Data.serialize(puts), gets)

        class BadType(object):
            """Bad object for type warning"""

        test_obj = BadType()
        with nt.assert_raises(LoadError) as err:
            Data.serialize(test_obj)
        nt.assert_equals(err.exception.message,
                         'cannot serialize index of type BadType')

    def test_pandas_series_loading(self):
        """Pandas Series objects are correctly loaded"""
        # Test valid series types
        name = ['_x', ' name']
        length = [0, 1, 2]
        index_key = [None, 'ix', 1]
        index_types = ['int', 'char', 'datetime', 'Timestamp']
        value_key = [None, 'x', 1]
        value_types = [
            'int', 'char', 'datetime', 'Timestamp', 'float',
            'numpy float', 'numpy int']

        series_info = product(
            name, length, index_key, index_types, value_key, value_types)
        for n, l, ikey, itype, vkey, vtype in series_info:
            index = sequences[itype](l)
            series = pd.Series(sequences[vtype](l), index=index, name=n,)

            ikey = ikey or Data._default_index_key
            vkey = vkey or series.name
            expected = [
                {ikey: Data.serialize(i), vkey: Data.serialize(v)}
                for i, v in zip(index, series)]

            data = Data.from_pandas(series, name=n, index_key=ikey,
                                    data_key=vkey)
            nt.assert_list_equal(expected, data.values)
            nt.assert_equal(n, data.name)
            data.to_json()

        # Missing a name
        series = pd.Series(np.random.randn(10))
        data = Data.from_pandas(series)
        nt.assert_equal(data.name, 'table')

    def test_pandas_dataframe_loading(self):
        """Pandas DataFrame objects are correctly loaded"""
        name = ['_x']
        length = [0, 1, 2]
        index_key = [None, 'ix', 1]
        index_types = ['int', 'char', 'datetime', 'Timestamp']
        column_types = ['int', 'char', 'datetime', 'Timestamp']

        # Leaving out some basic types here because we're not worried about
        # serialization.
        value_types = [
            'char', 'datetime', 'Timestamp', 'numpy float', 'numpy int']

        dataframe_info = product(
            name, length, length, index_key, index_types, column_types,
            value_types)
        for n, rows, cols, ikey, itype, ctype, vtype in dataframe_info:
            index = sequences[itype](rows)
            columns = sequences[ctype](cols)
            series = {
                c: pd.Series(sequences[vtype](rows), index=index, name=n)
                for c in columns}
            dataframe = pd.DataFrame(series)

            ikey = ikey or Data._default_index_key
            if cols == 0:
                expected = []
            else:
                expected = [
                    dict([(ikey, Data.serialize(index[i]))] +
                         [(str(c), Data.serialize(series[c][i]))
                          for c in columns])
                    for i in xrange(rows)]

            data = Data.from_pandas(dataframe, name=n, index_key=ikey)
            nt.assert_list_equal(expected, data.values)
            nt.assert_equal(n, data.name)
            data.to_json()

        # Missing a name
        dataframe = pd.DataFrame(np.random.randn(10, 3))
        data = Data.from_pandas(dataframe)
        nt.assert_equal(data.name, 'table')

        #Bad obj
        nt.assert_raises(ValueError, Data.from_pandas, {})

    def test_numpy_loading(self):
        """Numpy ndarray objects are correctly loaded"""
        test_data = np.random.randn(6, 3)
        index = xrange(test_data.shape[0])
        columns = ['a', 'b', 'c']

        data = Data.from_numpy(test_data, name='name', columns=columns)
        ikey = Data._default_index_key
        expected_values = [
            {ikey: i, 'a': row[0], 'b': row[1], 'c': row[2]}
            for i, row in zip(index, test_data.tolist())]
        nt.assert_list_equal(expected_values, data.values)
        nt.assert_equal('name', data.name)

        index_key = 'akey'
        data = Data.from_numpy(test_data, name='name', columns=columns,
                               index_key=index_key)
        expected_values = [
            {index_key: i, 'a': row[0], 'b': row[1], 'c': row[2]}
            for i, row in zip(index, test_data.tolist())]
        nt.assert_list_equal(expected_values, data.values)

        index = ['a', 'b', 'c', 'd', 'e', 'f']
        data = Data.from_numpy(test_data, name='name', index=index,
                               columns=columns)
        expected_values = [
            {ikey: i, 'a': row[0], 'b': row[1], 'c': row[2]}
            for i, row in zip(index, test_data.tolist())]
        nt.assert_list_equal(expected_values, data.values)

        #Bad loads
        with nt.assert_raises(LoadError) as err:
            Data.from_numpy(test_data, 'test', columns, index=xrange(4))
        nt.assert_equal(err.expected, LoadError)

        columns = ['a', 'b']
        with nt.assert_raises(LoadError) as err:
            Data.from_numpy(test_data, 'test', columns, index)
        nt.assert_equal(err.expected, LoadError)

    def test_from_mult_iters(self):
        """Test set of iterables"""
        test1 = Data.from_mult_iters(x=[0, 1, 2], y=[3, 4, 5])
        test2 = Data.from_mult_iters(apple=['one', 'two'], pear=[3, 4])
        values1 = [{'x': 0, 'y': 3}, {'x': 1, 'y': 4}, {'x': 2, 'y': 5}]
        values2 = [{'apple': 'one', 'pear': 3}, {'apple': 'two', 'pear': 4}]

        nt.assert_list_equal(test1.values, values1)
        nt.assert_list_equal(test2.values, values2)

        #Iter errors
        nt.assert_raises(ValueError, Data.from_mult_iters, x=[0], y=[1, 2])

    def test_stacked(self):
        """Testing stacked data import"""
        data1 = {'x': [1, 2, 3], 'y': [4, 5, 6], 'y2': [7, 8, 9]}
        data2 = {'x': ['one', 'two', 'three'], 'y': [1.0, 2.0, 3.0],
                 'y2': [4.0, 5.0, 6.0], 'y3': [7, 8, 9]}
        df1 = pd.DataFrame(data1)
        df2 = pd.DataFrame(data2)
        df3 = pd.DataFrame(data1, index=sequences['Timestamp'](3))

        stamps = []
        for stamp in sequences['Timestamp'](3):
            stamps.append(Data.serialize(stamp))

        #Input errors
        nt.assert_raises(ValueError, Data.stacked, data=data1)
        nt.assert_raises(ValueError, Data.stacked, x=[0, 1], y=[1])
        nt.assert_raises(ValueError, Data.stacked, data=df1, stack_on='x')

        truthy = {'data1_out':  [{'c': 0, 'x': 1, 'y': 4},
                                 {'c': 0, 'x': 2, 'y': 5},
                                 {'c': 0, 'x': 3, 'y': 6},
                                 {'c': 1, 'x': 1, 'y2': 7},
                                 {'c': 1, 'x': 2, 'y2': 8},
                                 {'c': 1, 'x': 3, 'y2': 9}],
                  'data2_out':  [{'c': 0, 'x': 'one', 'y': 1.0},
                                 {'c': 0, 'x': 'two', 'y': 2.0},
                                 {'c': 0, 'x': 'three', 'y': 3.0},
                                 {'c': 1, 'x': 'one', 'y3': 7},
                                 {'c': 1, 'x': 'two', 'y3': 8},
                                 {'c': 1, 'x': 'three', 'y3': 9},
                                 {'c': 2, 'x': 'one', 'y2': 4.0},
                                 {'c': 2, 'x': 'two', 'y2': 5.0},
                                 {'c': 2, 'x': 'three', 'y2': 6.0}],
                  'data2_out_2':  [{'c': 0, 'y': 1.0, 'y3': 7},
                                   {'c': 0, 'y': 2.0, 'y3': 8},
                                   {'c': 0, 'y': 3.0, 'y3': 9},
                                   {'c': 1, 'x': 'one', 'y3': 7},
                                   {'c': 1, 'x': 'two', 'y3': 8},
                                   {'c': 1, 'x': 'three', 'y3': 9},
                                   {'c': 2, 'y2': 4.0, 'y3': 7},
                                   {'c': 2, 'y2': 5.0, 'y3': 8},
                                   {'c': 2, 'y2': 6.0, 'y3': 9}],
                  'df3_out':  [{'c': 0, 'idx': stamps[0], 'x': 1},
                               {'c': 0, 'idx': stamps[1], 'x': 2},
                               {'c': 0, 'idx': stamps[2], 'x': 3},
                               {'c': 1, 'idx': stamps[0], 'y': 4},
                               {'c': 1, 'idx': stamps[1], 'y': 5},
                               {'c': 1, 'idx': stamps[2], 'y': 6},
                               {'c': 2, 'idx': stamps[0], 'y2': 7},
                               {'c': 2, 'idx': stamps[1], 'y2': 8},
                               {'c': 2, 'idx': stamps[2], 'y2': 9}]}

        stack_mat = [{'ref': 'data1_out', 'dat': {'data': data1,
                      'stack_on': 'x'}},
                     {'ref': 'data2_out', 'dat': {'data': data2,
                      'stack_on': 'x'}},
                     {'ref': 'data2_out_2', 'dat': {'data': data2,
                      'stack_on': 'y3'}},
                     {'ref': 'data1_out', 'dat': {'data': df1, 'stack_on': 'x',
                      'on_index': False}},
                     {'ref': 'df3_out', 'dat': {'data': df3}},
                     {'ref': 'data1_out', 'dat': {'x': [1, 2, 3], 'y': [4, 5, 6],
                      'y2': [7, 8, 9], 'stack_on': 'x'}}]

        for stacker in stack_mat:
            kwargs = stacker['dat']
            stack = Data.stacked(**kwargs)
            nt.assert_list_equal(truthy[stacker['ref']], stack.values)

    def test_from_iter(self):
        """Test data from single iter"""
        test = Data.from_iter([10, 20, 30])
        test1 = Data.from_iter((10, 20, 30))
        values = [{'x': 0, 'y': 10}, {'x': 1, 'y': 20}, {'x': 2, 'y': 30}]
        nt.assert_list_equal(test.values, values)
        nt.assert_list_equal(test1.values, values)

    def test_from_iter_pairs(self):
        """Test data from tuple of tuples"""
        test = Data.from_iter_pairs(((1, 10), (2, 20)))
        test1 = Data.from_iter_pairs([(1, 10), (2, 20)])
        test2 = Data.from_iter_pairs([[1, 10], [2, 20]])
        values = [{'x': 1, 'y': 10}, {'x': 2, 'y': 20}]

        nt.assert_list_equal(test.values, values)
        nt.assert_list_equal(test1.values, values)
        nt.assert_list_equal(test1.values, values)

    def test_from_dict(self):
        """Test data from dict"""
        test1 = Data.from_dict({'apples': 10, 'oranges': 20})
        test2 = Data.from_dict({1: 30, 2: 40})
        values1 = [{'x': 'apples', 'y': 10}, {'x': "oranges", 'y': 20}]
        values2 = [{'x': 1, 'y': 30}, {'x': 2, 'y': 40}]

        nt.assert_list_equal(test1.values, values1)
        nt.assert_list_equal(test2.values, values2)


class TestValueRef(object):
    """Test the ValueRef class"""

    def test_grammar_typechecking(self):
        """ValueRef fields are correctly type-checked"""
        grammar_types = [
            ('value', [str]),
            ('value', [int]),
            ('value', [float]),
            ('field', [str]),
            ('scale', [str]),
            ('mult', [int]),
            ('mult', [float]),
            ('offset', [int]),
            ('offset', [float]),
            ('band', [bool])]
        assert_grammar_typechecking(grammar_types, ValueRef())

    def test_json_serialization(self):
        """ValueRef JSON is correctly serialized"""
        vref = ValueRef()
        nt.assert_equal(json.dumps({}), vref.to_json(pretty_print=False))

        props = {
            'value': 'test-value',
            'band': True}
        vref = ValueRef(**props)
        nt.assert_equal(json.dumps(props), vref.to_json(pretty_print=False))

        props = {
            'value': 'test-value',
            'field': 'test-field',
            'scale': 'test-scale',
            'mult': 1.2,
            'offset': 4,
            'band': True}
        vref = ValueRef(**props)
        nt.assert_equal(json.dumps(props), vref.to_json(pretty_print=False))


class TestPropertySet(object):
    """Test the PropertySet Class"""

    def test_grammar_typechecking(self):
        """PropertySet fields are correctly type-checked"""
        # All fields must be ValueRef for Mark properties
        fields = [
            'x', 'x2', 'width', 'y', 'y2', 'height', 'opacity', 'fill',
            'fill_opacity', 'stroke', 'stroke_width', 'stroke_opacity',
            'size', 'shape', 'path', 'inner_radius', 'outer_radius',
            'start_angle', 'end_angle', 'interpolate', 'tension', 'url',
            'align', 'baseline', 'text', 'dx', 'dy', 'angle', 'font',
            'font_size', 'font_weight', 'font_style']
        grammar_types = [(f, [ValueRef]) for f in fields]
        assert_grammar_typechecking(grammar_types, PropertySet())

    def test_validation_checking(self):
        """ValueRef fields are grammar-checked"""

        grammar_errors = [('fill_opacity', ValueRef(value=-1), ValueError,
                           'fill_opacity must be between 0 and 1'),
                          ('fill_opacity', ValueRef(value=2), ValueError,
                           'fill_opacity must be between 0 and 1'),
                          ('stroke_width', ValueRef(value=-1), ValueError,
                           'stroke width cannot be negative'),
                          ('stroke_opacity', ValueRef(value=-1), ValueError,
                           'stroke_opacity must be between 0 and 1'),
                          ('stroke_opacity', ValueRef(value=2), ValueError,
                           'stroke_opacity must be between 0 and 1'),
                          ('size', ValueRef(value=-1), ValueError,
                           'size cannot be negative')]

        assert_grammar_validation(grammar_errors, PropertySet())

        bad_shape = ValueRef(value="BadShape")
        nt.assert_raises(ValueError, PropertySet, shape=bad_shape)

    def test_manual_typecheck(self):
        """Test manual typechecking for elements like marks"""

        test_attr = [('fill', ValueRef(value=1)),
                     ('fill_opacity', ValueRef(value='str')),
                     ('stroke', ValueRef(value=1)),
                     ('stroke_width', ValueRef(value='str')),
                     ('stroke_opacity', ValueRef(value='str')),
                     ('size', ValueRef(value='str')),
                     ('shape', ValueRef(value=1)),
                     ('path', ValueRef(value=1))]

        assert_manual_typechecking(test_attr, PropertySet())


class TestMarkProperties(object):
    """Test the MarkProperty Class"""

    def test_grammar_typechecking(self):
        """Test grammar of MarkProperty"""

        fields = ['enter', 'exit', 'update', 'hover']
        grammar_types = [(f, [PropertySet]) for f in fields]
        assert_grammar_typechecking(grammar_types, MarkProperties())


class TestMarkRef(object):
    """Test the MarkRef Class"""

    def test_grammar_typechecking(self):
        """Test grammar of MarkRef"""

        grammar_types = [('data', [str]), ('transform', [list])]
        assert_grammar_typechecking(grammar_types, MarkRef())


class TestMark(object):
    """Test Mark Class"""

    def test_grammar_typechecking(self):
        """Test grammar of Mark"""

        grammar_types = [('name', [str]), ('description', [str]),
                         ('from_', [MarkRef]),
                         ('properties', [MarkProperties]), ('key', [str]),
                         ('key', [str]), ('delay', [ValueRef]),
                         ('ease', [str])]
        assert_grammar_typechecking(grammar_types, Mark())

    def test_validation_checking(self):
        """Mark fields are grammar checked"""

        nt.assert_raises(ValueError, Mark, type='panda')


class TestDataRef(object):
    """Test DataRef class"""

    def test_grammar_typechecking(self):
        """Test grammar of DataRef"""

        grammar_types = [('data', [str]), ('field', [str])]
        assert_grammar_typechecking(grammar_types, DataRef())


class TestScale(object):
    """Test Scale class"""

    def test_grammar_typechecking(self):
        """Test grammar of Scale"""

        grammar_types = [('name', [str]), ('type', [str]),
                         ('domain', [list, DataRef]),
                         ('domain_min', [float, int, DataRef]),
                         ('domain_max', [float, int, DataRef]),
                         ('range', [list, str]),
                         ('range_min', [float, int, DataRef]),
                         ('range_max', [float, int, DataRef]),
                         ('reverse', [bool]), ('round', [bool]),
                         ('points', [bool]), ('clamp', [bool]),
                         ('nice', [bool, str]),
                         ('exponent', [float, int]),
                         ('zero', [bool])]

        assert_grammar_typechecking(grammar_types, Scale())


class TestAxisProperties(object):
    """Test AxisProperties Class"""

    def test_grammar_typechecking(self):
        """Test grammar of AxisProperties"""

        grammar_types = [('major_ticks', [PropertySet]),
                         ('minor_ticks', [PropertySet]),
                         ('label', [PropertySet]),
                         ('axis', [PropertySet])]

        assert_grammar_typechecking(grammar_types, AxisProperties())


class TestAxis(object):
    """Test Axis Class"""

    def test_grammar_typechecking(self):
        """Test grammar of Axis"""

        grammar_types = [('scale', [str]),
                         ('orient', [str]), ('format', [str]),
                         ('ticks', [int]), ('values', [list]),
                         ('subdivide', [int, float]),
                         ('tick_padding', [int]), ('tick_size', [int]),
                         ('tick_size_major', [int]),
                         ('tick_size_minor', [int]),
                         ('tick_size_end', [int]),
                         ('offset', [int]),
                         ('properties', [AxisProperties])]

        assert_grammar_typechecking(grammar_types, Axis())
