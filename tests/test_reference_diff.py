"""快速实现与参考实现（0101 字符串切片）的逐字段对照。

随机生成「数据 + 字段表」，比对解包值、打包结果与错误类型。
"""

import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import reference  # noqa: E402
from bitfield.unpack import BitfieldError, Field, pack, unpack  # noqa: E402

ROUNDS = 10000


def random_field(rng, offset, width):
    kind = rng.choice(["u", "u", "s", "s", "f"])
    frac = rng.randint(0, min(8, width - 1)) if kind == "f" else 0
    return Field("f%d" % offset, offset, width, kind, frac)


def random_layout(rng, total_bits):
    """生成不重叠的字段表，声明顺序随机。"""
    fields = []
    cursor = 0
    while cursor < total_bits and len(fields) < 12:
        width = rng.randint(1, min(24, total_bits - cursor))
        fields.append(random_field(rng, cursor, width))
        cursor += width + rng.randint(0, 3)
    rng.shuffle(fields)
    return fields


def random_values(rng, fields):
    values = {}
    for field in fields:
        if field.kind == "s":
            values[field.name] = rng.randint(-(1 << (field.width - 1)), (1 << (field.width - 1)) - 1)
        elif field.kind == "f":
            quantum = rng.randint(0, (1 << field.width) - 1)
            values[field.name] = quantum / (1 << field.frac)
        else:
            values[field.name] = rng.randint(0, (1 << field.width) - 1)
    return values


def assert_same_outcome(test, fast_call, ref_call):
    fast_err = ref_err = None
    fast_out = ref_out = None
    try:
        fast_out = fast_call()
    except BitfieldError as error:
        fast_err = error
    try:
        ref_out = ref_call()
    except BitfieldError as error:
        ref_err = error
    test.assertEqual(fast_err is None, ref_err is None,
                     "错误类型不一致：%r vs %r" % (fast_err, ref_err))
    if fast_err is None:
        test.assertEqual(fast_out, ref_out)
        return fast_out
    return None


class DifferentialTest(unittest.TestCase):
    def test_random_valid_rounds(self):
        rng = random.Random(20260928)
        for _ in range(ROUNDS):
            data = bytes(rng.getrandbits(8) for _ in range(rng.randint(1, 12)))
            total_bits = len(data) * 8
            fields = random_layout(rng, total_bits)
            if not fields:
                continue
            order = rng.choice(["msb", "lsb"])
            values = assert_same_outcome(
                self,
                lambda: unpack(data, fields, order),
                lambda: reference.unpack(data, fields, order),
            )
            packed = assert_same_outcome(
                self,
                lambda: pack(values, fields, order),
                lambda: reference.pack(values, fields, order),
            )
            # 往返不变量：unpack(pack(values)) == values
            self.assertEqual(unpack(packed, fields, order), values)
            # 随机值打包也要一致
            raw_values = random_values(rng, fields)
            packed2 = assert_same_outcome(
                self,
                lambda: pack(raw_values, fields, order),
                lambda: reference.pack(raw_values, fields, order),
            )
            self.assertEqual(unpack(packed2, fields, order), raw_values)

    def test_random_error_rounds(self):
        rng = random.Random(77031)
        for _ in range(ROUNDS):
            data = bytes(rng.getrandbits(8) for _ in range(rng.randint(1, 4)))
            total_bits = len(data) * 8
            kind_of_error = rng.randrange(3)
            if kind_of_error == 0:
                # 越界
                offset = rng.randint(0, total_bits + 8)
                width = rng.randint(total_bits - offset + 1, total_bits - offset + 16)
                fields = [Field("c", offset, width)]
            elif kind_of_error == 1:
                # 重叠
                a_off = rng.randint(0, total_bits - 1)
                b_off = rng.randint(0, total_bits - 1)
                fields = [
                    Field("a", a_off, rng.randint(1, total_bits - a_off)),
                    Field("b", b_off, rng.randint(1, total_bits - b_off)),
                ]
                if not (a_off < b_off + fields[1].width and b_off < a_off + fields[0].width):
                    continue
            else:
                # 重名
                fields = [Field("dup", 0, 4), Field("dup", 4, 4)]
            order = rng.choice(["msb", "lsb"])
            assert_same_outcome(
                self,
                lambda: unpack(data, fields, order),
                lambda: reference.unpack(data, fields, order),
            )

    def test_error_messages_for_canonical_cases(self):
        # 题目指定的消息口径逐字比对
        fast_err = ref_err = None
        try:
            unpack(bytes.fromhex("0F"), [Field("c", 12, 8)])
        except BitfieldError as error:
            fast_err = str(error)
        try:
            reference.unpack(bytes.fromhex("0F"), [Field("c", 12, 8)])
        except BitfieldError as error:
            ref_err = str(error)
        self.assertEqual(fast_err, "字段 c 越界（需要 20 位，只有 8 位）")
        self.assertEqual(fast_err, ref_err)


if __name__ == "__main__":
    unittest.main()
