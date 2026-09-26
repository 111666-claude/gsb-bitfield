import unittest

from bitfield.unpack import BitfieldError, parse_field, unpack


class ParseTest(unittest.TestCase):
    def test_parse_unsigned(self):
        field = parse_field("a:0:4")
        self.assertEqual((field.name, field.offset, field.width, field.signed), ("a", 0, 4, False))

    def test_parse_signed(self):
        self.assertTrue(parse_field("a:0:4:s").signed)

    def test_reject_bad_spec(self):
        with self.assertRaises(BitfieldError):
            parse_field("a:0")


class UnpackTest(unittest.TestCase):
    def test_whole_byte(self):
        values = unpack(bytes([0xF0]), [parse_field("b:0:8")])
        self.assertEqual(values["b"], 240)

    def test_high_nibble(self):
        values = unpack(bytes([0xF0]), [parse_field("hi:0:4")])
        self.assertEqual(values["hi"], 15)

    def test_low_nibble(self):
        values = unpack(bytes([0x0F]), [parse_field("lo:4:4")])
        self.assertEqual(values["lo"], 15)

    def test_positive_signed(self):
        values = unpack(bytes([0x70]), [parse_field("s:0:4:s")])
        self.assertEqual(values["s"], 7)

    def test_multiple_fields(self):
        values = unpack(bytes([0x12, 0x34]), [parse_field("a:0:8"), parse_field("b:8:8")])
        self.assertEqual((values["a"], values["b"]), (18, 52))
