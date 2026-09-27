import random
import unittest

import reference
from bitfield.unpack import BitfieldError, Field, pack, unpack


def random_fields(rng, nbytes):
    fields = []
    for index in range(rng.randint(1, 5)):
        fields.append(Field(
            "f%d" % index,
            rng.randint(0, nbytes * 8 + 4),
            rng.randint(1, 16),
            rng.choice(["u", "s", "f"]),
        ))
    return fields


class DifferentialTest(unittest.TestCase):
    def test_random_against_reference(self):
        rng = random.Random(20260928)
        for case in range(10000):
            nbytes = rng.randint(1, 8)
            data = bytes(rng.getrandbits(8) for _ in range(nbytes))
            order = rng.choice(["msb", "lsb"])
            frac = rng.randint(0, 6)
            fields = random_fields(rng, nbytes)

            got_err = want_err = None
            try:
                got = unpack(data, fields, order=order, frac=frac)
            except BitfieldError as error:
                got_err = error
            try:
                want = reference.ref_unpack(data, fields, order=order, frac=frac)
            except BitfieldError as error:
                want_err = error
            self.assertEqual(
                got_err is None, want_err is None,
                "case %d: 错误类型不一致 fields=%r order=%s" % (case, fields, order),
            )
            if got_err is not None:
                continue
            self.assertEqual(got, want, "case %d" % case)

            packed_fast = pack(fields, got, order=order, frac=frac)
            packed_ref = reference.ref_pack(fields, got, order=order, frac=frac)
            self.assertEqual(packed_fast, packed_ref, "case %d" % case)

            again = unpack(packed_fast, fields, order=order, frac=frac)
            for field in fields:
                if field.ftype == "f":
                    self.assertLess(
                        abs(again[field.name] - got[field.name]),
                        1.0 / (1 << frac),
                        "case %d 字段 %s" % (case, field.name),
                    )
                else:
                    self.assertEqual(again[field.name], got[field.name], "case %d" % case)

            victim = rng.choice(fields)
            bad_values = dict(got)
            bad_values[victim.name] = (1 << victim.width) + rng.randint(0, 100)
                # 越界值：u 必然超界；s/f 也必然超界（远大于 2^(width-1)）
            for impl_pack in (pack, reference.ref_pack):
                with self.assertRaises(BitfieldError, msg="case %d 越界值未报错" % case):
                    impl_pack(fields, bad_values, order=order, frac=frac)


if __name__ == "__main__":
    unittest.main()
