import json
import subprocess
import sys
import unittest

from bitfield.unpack import BitfieldError, parse_field, pack, unpack


def pf(spec, default_frac=0):
    return parse_field(spec, default_frac)


class SignedTest(unittest.TestCase):
    def test_all_ones_is_minus_one(self):
        self.assertEqual(unpack(bytes.fromhex("F0"), [pf("a:0:4:s")])["a"], -1)

    def test_sign_bit_only_is_min(self):
        self.assertEqual(unpack(bytes.fromhex("80"), [pf("a:0:4:s")])["a"], -8)

    def test_max_positive(self):
        self.assertEqual(unpack(bytes.fromhex("70"), [pf("a:0:4:s")])["a"], 7)

    def test_full_width_signed(self):
        self.assertEqual(unpack(bytes([0xFF]), [pf("a:0:8:s")])["a"], -1)
        self.assertEqual(unpack(bytes([0x80]), [pf("a:0:8:s")])["a"], -128)

    def test_signed_cross_byte(self):
        # 0xFFF0 的 12 位有符号字段 1111_1111_1111 -> -1
        self.assertEqual(unpack(bytes.fromhex("FFF0"), [pf("a:0:12:s")])["a"], -1)


class OrderTest(unittest.TestCase):
    def test_default_is_msb(self):
        self.assertEqual(unpack(bytes([0xF0]), [pf("b:0:8")])["b"], 240)
        self.assertEqual(unpack(bytes([0xF0]), [pf("hi:0:4")])["hi"], 15)
        self.assertEqual(unpack(bytes([0x0F]), [pf("lo:4:4")])["lo"], 15)

    def test_lsb_bit_zero_is_lowest(self):
        # LSB0：位 0 是首字节最低有效位，0x0F 的位 0..3 才是 1111
        self.assertEqual(unpack(bytes([0x0F]), [pf("a:0:4:s")], order="lsb")["a"], -1)
        self.assertEqual(unpack(bytes([0xF0]), [pf("hi:0:4")], order="lsb")["hi"], 0)
        self.assertEqual(unpack(bytes([0x0F]), [pf("lo:4:4")], order="lsb")["lo"], 0)

    def test_lsb_cross_byte(self):
        # 0xF0 0x01：LSB0 下流位 4..11 为 1,1,1,1,1,0,0,0，值位 0..7 -> 0b00011111
        self.assertEqual(unpack(bytes([0xF0, 0x01]), [pf("x:4:8")], order="lsb")["x"], 31)

    def test_bad_order(self):
        with self.assertRaises(BitfieldError):
            unpack(b"\x00", [pf("a:0:1")], order="big")


class FixedPointTest(unittest.TestCase):
    def test_fixed_point_per_field_frac(self):
        self.assertEqual(unpack(bytes([0xC0]), [pf("x:0:4:f:2")])["x"], 3.0)
        self.assertEqual(unpack(bytes([0x03]), [pf("x:0:8:f:4")])["x"], 0.1875)

    def test_fixed_point_default_frac(self):
        self.assertEqual(unpack(bytes([0x03]), [pf("x:0:8:f", default_frac=4)])["x"], 0.1875)

    def test_fixed_point_zero_frac_is_int(self):
        self.assertEqual(unpack(bytes([0x70]), [pf("x:0:4:f")])["x"], 7.0)

    def test_negative_frac_rejected(self):
        with self.assertRaises(BitfieldError):
            pf("x:0:4:f:-1")


class ParseTest(unittest.TestCase):
    def test_kinds(self):
        self.assertEqual(pf("a:0:4").kind, "u")
        self.assertEqual(pf("a:0:4:u").kind, "u")
        self.assertEqual(pf("a:0:4:s").kind, "s")
        self.assertEqual(pf("a:0:4:f:3").kind, "f")
        self.assertEqual(pf("a:0:4:f:3").frac, 3)

    def test_signed_property_compat(self):
        self.assertTrue(pf("a:0:4:s").signed)
        self.assertFalse(pf("a:0:4").signed)

    def test_bad_specs_name_the_field(self):
        for spec in ("a:0", "a:x:4", "a:0:y", "a:0:4:z", ":0:4", "a:0:4:s:1:2"):
            with self.assertRaises(BitfieldError, msg=spec):
                pf(spec)

    def test_negative_offset_and_width(self):
        with self.assertRaises(BitfieldError):
            pf("a:-1:4")
        with self.assertRaises(BitfieldError):
            pf("a:0:0")
        with self.assertRaises(BitfieldError):
            pf("a:0:-3")


class BoundsTest(unittest.TestCase):
    def test_out_of_bounds_message(self):
        with self.assertRaises(BitfieldError) as ctx:
            unpack(bytes.fromhex("0F"), [pf("c:12:8")])
        self.assertEqual(str(ctx.exception), "字段 c 越界（需要 20 位，只有 8 位）")

    def test_exact_fit_ok(self):
        self.assertEqual(unpack(bytes.fromhex("FF"), [pf("c:0:8")])["c"], 255)

    def test_one_bit_past_end(self):
        with self.assertRaises(BitfieldError):
            unpack(bytes.fromhex("FF"), [pf("c:0:9")])


class OverlapTest(unittest.TestCase):
    def test_overlap_reports_both_names(self):
        with self.assertRaises(BitfieldError) as ctx:
            unpack(bytes.fromhex("FFFF"), [pf("a:0:8"), pf("b:4:8")])
        message = str(ctx.exception)
        self.assertIn("a", message)
        self.assertIn("b", message)
        self.assertIn("重叠", message)

    def test_adjacent_fields_ok(self):
        values = unpack(bytes.fromhex("FFFF"), [pf("a:0:8"), pf("b:8:8")])
        self.assertEqual((values["a"], values["b"]), (255, 255))

    def test_duplicate_name_rejected(self):
        with self.assertRaises(BitfieldError):
            unpack(b"\xff", [pf("a:0:4"), pf("a:4:4")])

    def test_empty_fields_rejected(self):
        with self.assertRaises(BitfieldError):
            unpack(b"\xff", [])


class PackTest(unittest.TestCase):
    def test_pack_signed(self):
        self.assertEqual(pack({"a": -1}, [pf("a:0:4:s")]).hex(), "f0")
        self.assertEqual(pack({"a": -8}, [pf("a:0:4:s")]).hex(), "80")

    def test_pack_unsigned(self):
        self.assertEqual(pack({"b": 240}, [pf("b:0:8")]).hex(), "f0")

    def test_pack_fixed_point(self):
        self.assertEqual(pack({"x": 3.0}, [pf("x:0:4:f:2")]).hex(), "c0")
        self.assertEqual(pack({"x": 0.1875}, [pf("x:0:8:f:4")]).hex(), "03")

    def test_pack_lsb(self):
        self.assertEqual(pack({"a": -1}, [pf("a:0:4:s")], order="lsb").hex(), "0f")

    def test_pack_out_of_range(self):
        with self.assertRaises(BitfieldError):
            pack({"a": 8}, [pf("a:0:4:s")])
        with self.assertRaises(BitfieldError):
            pack({"a": -9}, [pf("a:0:4:s")])
        with self.assertRaises(BitfieldError):
            pack({"a": 16}, [pf("a:0:4")])
        with self.assertRaises(BitfieldError):
            pack({"a": -1}, [pf("a:0:4")])
        with self.assertRaises(BitfieldError):
            pack({"x": 4.0}, [pf("x:0:4:f:2")])

    def test_pack_unknown_field(self):
        with self.assertRaises(BitfieldError):
            pack({"nope": 1}, [pf("a:0:4")])

    def test_pack_missing_fields_are_zero(self):
        self.assertEqual(pack({"a": 1}, [pf("a:0:4"), pf("b:4:4")]).hex(), "10")

    def test_roundtrip_signed_and_fixed(self):
        fields = [pf("a:0:5:s"), pf("b:5:11"), pf("c:16:10:f:3"), pf("d:26:6:s")]
        data = bytes.fromhex("deadbeef")
        for order in ("msb", "lsb"):
            values = unpack(data, fields, order)
            self.assertEqual(unpack(pack(values, fields, order), fields, order), values)

    def test_roundtrip_fixed_point_precision(self):
        fields = [pf("c:0:12:f:5")]
        values = unpack(bytes.fromhex("ABCD"), fields)
        self.assertEqual(unpack(pack(values, fields), fields), values)


class CliTest(unittest.TestCase):
    def run_cli(self, *argv):
        return subprocess.run(
            [sys.executable, "-m", "bitfield.cli", *argv],
            capture_output=True, text=True, cwd=_repo_root(),
        )

    def test_cli_unpack_unchanged_format(self):
        result = self.run_cli("--hex", "F0", "--fields", "b:0:8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"b": 240})

    def test_cli_signed_fixed(self):
        result = self.run_cli("--hex", "F0", "--fields", "a:0:4:s")
        self.assertEqual(json.loads(result.stdout), {"a": -1})

    def test_cli_lsb(self):
        result = self.run_cli("--hex", "0F", "--fields", "a:0:4:s", "--order", "lsb")
        self.assertEqual(json.loads(result.stdout), {"a": -1})

    def test_cli_out_of_bounds(self):
        result = self.run_cli("--hex", "0F", "--fields", "c:12:8")
        self.assertEqual(result.returncode, 1)
        self.assertIn("字段 c 越界（需要 20 位，只有 8 位）", result.stderr)

    def test_cli_fixed_point_with_frac_flag(self):
        result = self.run_cli("--hex", "03", "--fields", "x:0:8:f", "--frac", "4")
        self.assertEqual(json.loads(result.stdout), {"x": 0.1875})

    def test_cli_pack_roundtrip(self):
        packed = self.run_cli("--fields", "a:0:4:s,b:4:4", "--pack", "a=-1,b=3")
        self.assertEqual(packed.returncode, 0, packed.stderr)
        back = self.run_cli("--hex", packed.stdout.strip(), "--fields", "a:0:4:s,b:4:4")
        self.assertEqual(json.loads(back.stdout), {"a": -1, "b": 3})

    def test_cli_pack_out_of_range(self):
        result = self.run_cli("--fields", "a:0:4:s", "--pack", "a=8")
        self.assertEqual(result.returncode, 1)
        self.assertIn("超出", result.stderr)

    def test_cli_needs_hex_or_pack(self):
        result = self.run_cli("--fields", "a:0:4")
        self.assertEqual(result.returncode, 2)


def _repo_root():
    import os
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


if __name__ == "__main__":
    unittest.main()
