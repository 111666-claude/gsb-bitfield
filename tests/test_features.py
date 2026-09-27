import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout

from bitfield.cli import main
from bitfield.unpack import BitfieldError, Field, pack, parse_field, unpack


class TwosComplementTest(unittest.TestCase):
    def test_minus_one(self):
        self.assertEqual(unpack(bytes([0x0F]), [parse_field("a:4:4:s")])["a"], -1)

    def test_minus_eight(self):
        self.assertEqual(unpack(bytes([0x80]), [parse_field("a:0:4:s")])["a"], -8)

    def test_full_range(self):
        self.assertEqual(unpack(bytes([0x70]), [parse_field("a:0:4:s")])["a"], 7)


class BitOrderTest(unittest.TestCase):
    def test_msb_default(self):
        self.assertEqual(unpack(bytes([0x01]), [parse_field("a:0:8")])["a"], 1)

    def test_lsb(self):
        self.assertEqual(unpack(bytes([0x01]), [parse_field("a:0:8")], order="lsb")["a"], 1)
        self.assertEqual(unpack(bytes([0x80]), [parse_field("a:0:8")], order="lsb")["a"], 128)
        self.assertEqual(unpack(bytes([0x01]), [parse_field("a:7:1")], order="lsb")["a"], 0)
        self.assertEqual(unpack(bytes([0x01]), [parse_field("a:0:1")], order="lsb")["a"], 1)

    def test_lsb_cross_byte(self):
        fields = [parse_field("a:4:8")]
        self.assertEqual(unpack(bytes([0x21, 0x43]), fields, order="lsb")["a"], 0x32)
        self.assertEqual(unpack(bytes([0x12, 0x34]), fields)["a"], 0x23)

    def test_bad_order(self):
        with self.assertRaises(BitfieldError):
            unpack(bytes([0x00]), [parse_field("a:0:1")], order="middle")


class FixedPointTest(unittest.TestCase):
    def test_unsigned_like_positive(self):
        fields = [parse_field("a:0:8:f")]
        self.assertEqual(unpack(bytes([0x60]), fields, frac=4)["a"], 6.0)

    def test_negative_fixed(self):
        fields = [parse_field("a:0:8:f")]
        self.assertEqual(unpack(bytes([0xF0]), fields, frac=4)["a"], -1.0)

    def test_zero_frac_gives_int(self):
        fields = [parse_field("a:0:8:f")]
        self.assertEqual(unpack(bytes([0x05]), fields)["a"], 5)


class BoundsAndOverlapTest(unittest.TestCase):
    def test_out_of_bounds_message(self):
        with self.assertRaises(BitfieldError) as ctx:
            unpack(bytes([0x0F]), [parse_field("c:12:8")])
        self.assertEqual(str(ctx.exception), "字段 c 越界（需要 20 位，只有 8 位）")

    def test_exact_fit_ok(self):
        self.assertEqual(unpack(bytes([0xFF]), [parse_field("a:0:8")])["a"], 255)

    def test_overlap_message(self):
        with self.assertRaises(BitfieldError) as ctx:
            unpack(bytes([0x00, 0x00]), [parse_field("a:0:8"), parse_field("b:4:8")])
        message = str(ctx.exception)
        self.assertIn("a", message)
        self.assertIn("b", message)
        self.assertIn("重叠", message)

    def test_nested_overlap_detected(self):
        fields = [parse_field("a:0:16"), parse_field("b:1:2"), parse_field("c:3:4")]
        with self.assertRaises(BitfieldError):
            unpack(bytes(4), fields)


class ParseTest(unittest.TestCase):
    def test_non_numeric_mentions_field(self):
        with self.assertRaises(BitfieldError) as ctx:
            parse_field("a:x:4")
        self.assertIn("a", str(ctx.exception))

    def test_negative_width(self):
        with self.assertRaises(BitfieldError):
            parse_field("a:0:-2")

    def test_zero_width(self):
        with self.assertRaises(BitfieldError):
            parse_field("a:0:0")

    def test_negative_offset(self):
        with self.assertRaises(BitfieldError):
            parse_field("a:-1:4")

    def test_bad_type(self):
        with self.assertRaises(BitfieldError):
            parse_field("a:0:4:x")

    def test_types(self):
        self.assertEqual(parse_field("a:0:4").ftype, "u")
        self.assertEqual(parse_field("a:0:4:u").ftype, "u")
        self.assertEqual(parse_field("a:0:4:s").ftype, "s")
        self.assertEqual(parse_field("a:0:4:f").ftype, "f")


class PackTest(unittest.TestCase):
    def test_roundtrip_signed(self):
        fields = [parse_field("a:0:4:s"), parse_field("b:4:4")]
        data = pack(fields, {"a": -1, "b": 3})
        self.assertEqual(data, bytes([0xF3]))
        self.assertEqual(unpack(data, fields), {"a": -1, "b": 3})

    def test_roundtrip_lsb(self):
        fields = [parse_field("a:0:3:s"), parse_field("b:3:9"), parse_field("c:12:4:f")]
        values = {"a": -4, "b": 300, "c": 1.5}
        data = pack(fields, values, order="lsb", frac=2)
        back = unpack(data, fields, order="lsb", frac=2)
        self.assertEqual(back, values)

    def test_roundtrip_fixed_precision(self):
        fields = [parse_field("a:0:8:f")]
        data = pack(fields, {"a": 0.3}, frac=4)
        back = unpack(data, fields, frac=4)["a"]
        self.assertLess(abs(back - 0.3), 1.0 / 16)

    def test_value_out_of_range(self):
        fields = [parse_field("a:0:4")]
        with self.assertRaises(BitfieldError):
            pack(fields, {"a": 16})
        with self.assertRaises(BitfieldError):
            pack(fields, {"a": -1})

    def test_signed_out_of_range(self):
        fields = [parse_field("a:0:4:s")]
        with self.assertRaises(BitfieldError):
            pack(fields, {"a": 8})
        with self.assertRaises(BitfieldError):
            pack(fields, {"a": -9})
        self.assertEqual(unpack(pack(fields, {"a": -8}), fields)["a"], -8)

    def test_fixed_out_of_range(self):
        fields = [parse_field("a:0:8:f")]
        with self.assertRaises(BitfieldError):
            pack(fields, {"a": 8.0}, frac=4)

    def test_pack_overlap_rejected(self):
        fields = [parse_field("a:0:8"), parse_field("b:4:8")]
        with self.assertRaises(BitfieldError):
            pack(fields, {"a": 1, "b": 2})

    def test_missing_value(self):
        with self.assertRaises(BitfieldError):
            pack([parse_field("a:0:4")], {})

    def test_pack_size_from_fields(self):
        fields = [parse_field("a:12:4")]
        self.assertEqual(len(pack(fields, {"a": 1})), 2)


class CliTest(unittest.TestCase):
    def run_cli(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_unpack_default_output(self):
        code, out, _ = self.run_cli(["--hex", "F0", "--fields", "a:0:4:s"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), {"a": -1})

    def test_unpack_out_of_bounds_exit_code(self):
        code, _, err = self.run_cli(["--hex", "0F", "--fields", "c:12:8"])
        self.assertEqual(code, 1)
        self.assertIn("字段 c 越界（需要 20 位，只有 8 位）", err)

    def test_pack_then_unpack(self):
        code, out, _ = self.run_cli(["--fields", "a:0:4:s,b:4:4", "--pack", "a=-1,b=3"])
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "f3")
        code, out, _ = self.run_cli(["--hex", out.strip(), "--fields", "a:0:4:s,b:4:4"])
        self.assertEqual(json.loads(out), {"a": -1, "b": 3})

    def test_pack_lsb(self):
        code, out, _ = self.run_cli(
            ["--fields", "a:0:8", "--pack", "a=1", "--order", "lsb"])
        self.assertEqual((code, out.strip()), (0, "01"))

    def test_pack_out_of_range_exit_code(self):
        code, _, err = self.run_cli(["--fields", "a:0:4", "--pack", "a=16"])
        self.assertEqual(code, 1)
        self.assertIn("超出", err)


class ScaleTest(unittest.TestCase):
    def test_100k_fields_1mb(self):
        count, width, stride = 100000, 64, 80
        data = bytes((i * 37 + 11) & 0xFF for i in range(1 << 20))
        fields = [Field("f%d" % i, i * stride, width, "u") for i in range(count)]
        values = unpack(data, fields)
        self.assertEqual(len(values), count)
        packed = pack(fields, values)
        self.assertEqual(unpack(packed, fields), values)


if __name__ == "__main__":
    unittest.main()
