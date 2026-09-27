"""规模：10 万字段、1 MB 数据，unpack 与 pack 都要线性完成。"""

import random
import time
import unittest

from bitfield.unpack import Field, pack, unpack

FIELD_COUNT = 100_000
DATA_BYTES = 1 << 20  # 1 MB
TIME_BUDGET = 20.0


def make_fields(total_bits, count, rng):
    fields = []
    base, remainder = divmod(total_bits, count)
    cursor = 0
    for index in range(count):
        width = base + (1 if index < remainder else 0)
        kind = ("u", "s")[index % 2]
        fields.append(Field("f%d" % index, cursor, width, kind))
        cursor += width
    return fields


class ScaleTest(unittest.TestCase):
    def test_unpack_and_pack_linear(self):
        rng = random.Random(7)
        data = rng.randbytes(DATA_BYTES)
        fields = make_fields(DATA_BYTES * 8, FIELD_COUNT, rng)
        self.assertEqual(len(fields), FIELD_COUNT)

        start = time.monotonic()
        values = unpack(data, fields)
        unpack_seconds = time.monotonic() - start

        start = time.monotonic()
        packed = pack(values, fields)
        pack_seconds = time.monotonic() - start

        self.assertEqual(len(values), FIELD_COUNT)
        self.assertEqual(len(packed), DATA_BYTES)
        # 往返不变量在大规模下同样成立
        self.assertEqual(unpack(packed, fields), values)
        self.assertLess(unpack_seconds + pack_seconds, TIME_BUDGET,
                        "unpack %.1fs + pack %.1fs 超出预算" % (unpack_seconds, pack_seconds))


if __name__ == "__main__":
    unittest.main()
