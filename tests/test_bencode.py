from zhongzi import bencode
from collections import OrderedDict
import unittest


class DecodeTests(unittest.TestCase):
    def test_peek_iis_idempotent(self):
        decoder = bencode.Decoder(b'12')
        
        self.assertEqual(b'1', decoder._peek())
        self.assertEqual(b'1', decoder._peek())

    def test_peek_should_handle_end(self):
        decoder = bencode.Decoder(b'1')
        decoder._consume()

        self.assertEqual(None, decoder._peek())

    def test_read_until_found(self):
        decoder = bencode.Decoder(b'123456')

        self.assertEqual(b'123', decoder._read_until(b'4'))

    def test_read_until_not_found(self):
        decoder = bencode.Decoder(b'123456')

        with self.assertRaises(RuntimeError):
            decoder._read_until(b'7')

    def test_empty_string(self):
        decoder = bencode.Decoder(b'')

        with self.assertRaises(EOFError):
            decoder.decode()

    def test_integer(self):
        decoder = bencode.Decoder(b'i123e')

        self.assertEqual(123, decoder.decode())

    def test_string(self):
        res = bencode.Decoder(b'2:ee').decode()

        self.assertEqual(b'ee', res)

    def test_min_string(self):
        res = bencode.Decoder(b'1:a').decode()

        self.assertEqual(b'a', res)

    def test_string_with_space(self):
        res = bencode.Decoder(b'12:middle eartj').decode()

        self.assertEqual(b'middle eartj', res)

    def test_list(self):
        res = bencode.Decoder(b'l4:spam4:eggsi123ee').decode()

        self.assertEqual(len(res), 3)
        self.assertEqual(res[0], b'spam')
        self.assertEqual(res[1], b'eggs')
        self.assertEqual(res[2], 123)

    def test_dict(self):
        res = bencode.Decoder(b'd3:cow3:moo4:spam4:eggse').decode()

        self.assertTrue(isinstance(res, dict))
        self.assertEqual(res[b'cow'], b'moo')
        self.assertEqual(res[b'spam'], b'eggs')

    
class EncodeTests(unittest.TestCase):
    def test_empty_encoding(self):
        res = bencode.Encoder(None).encode()

        self.assertEqual(res, None)

    def test_integer(self):
        res = bencode.Encoder(123).encode()

        self.assertEqual(res, b'i123e')

    def test_string(self):
        res = bencode.Encoder('middle err').encode()

        self.assertEqual(res, b'10:middle err')

    def test_list(self):
        res = bencode.Encoder(['ss', 'sdd', 2333]).encode()

        self.assertEqual(res, b'l2:ss3:sddi2333ee')

    def test_dict(self):

        d = OrderedDict()
        d['ee'] = 'mgo'
        d['cf'] = 'redis'

        res = bencode.Encoder(d).encode()

        self.assertEqual(res, b'd2:ee3:mgo2:cf5:redise')

    def test_nested_structure(self):
        outer = OrderedDict()
        b = OrderedDict()
        b['ba'] = 'foo'
        b['bb'] = 'bar'
        outer['a'] = 123
        outer['b'] = b
        outer['c'] = [['a', 'b'], 'z']
        res = bencode.Encoder(outer).encode()

        self.assertEqual(res,
                         b'd1:ai123e1:bd2:ba3:foo2:bb3:bare1:cll1:a1:be1:zee')