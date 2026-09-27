"""参考实现：正向把整串转成 0101 字符串再切片，反向按位写回。

刻意走最直接（也最慢）的路线，与 bitfield.unpack 的快速实现互相印证。
校验口径与快速实现一致，错误类型同为 BitfieldError。
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bitfield.unpack import BitfieldError, parse_field  # noqa: F401,E402


def _validate(fields):
    if not fields:
        raise BitfieldError("字段表为空")
    seen = set()
    for field in fields:
        if not field.name:
            raise BitfieldError("字段名不能为空")
        if field.name in seen:
            raise BitfieldError("字段名重复：%s" % field.name)
        seen.add(field.name)
        if field.offset < 0:
            raise BitfieldError("字段 %s 偏移量必须为非负整数" % field.name)
        if field.width < 1:
            raise BitfieldError("字段 %s 位宽必须 >= 1" % field.name)
        if field.kind not in ("u", "s", "f"):
            raise BitfieldError("字段 %s 类型应为 u/s/f：%r" % (field.name, field.kind))
        if field.frac < 0:
            raise BitfieldError("字段 %s 定点小数位数必须为非负整数" % field.name)
    for i, a in enumerate(fields):
        for b in fields[i + 1:]:
            if a.offset < b.offset + b.width and b.offset < a.offset + a.width:
                raise BitfieldError("字段 %s 与 %s 覆盖位重叠" % (a.name, b.name))


def _bits(data, order):
    if order == "msb":
        return "".join(format(byte, "08b") for byte in data)
    if order == "lsb":
        return "".join(format(byte, "08b")[::-1] for byte in data)
    raise BitfieldError("位序应为 msb 或 lsb：%r" % order)


def _decode(field, raw):
    if field.kind == "s" and raw >> (field.width - 1):
        return raw - (1 << field.width)
    if field.kind == "f":
        return raw / (1 << field.frac)
    return raw


def unpack(data, fields, order="msb"):
    _validate(fields)
    bits = _bits(data, order)
    out = {}
    for field in fields:
        end = field.offset + field.width
        if end > len(bits):
            raise BitfieldError(
                "字段 %s 越界（需要 %d 位，只有 %d 位）" % (field.name, end, len(bits))
            )
        raw = int(bits[field.offset:end], 2)
        if order == "lsb":
            # LSB0：字段第一个流位是最低有效位
            raw = int(bits[field.offset:end][::-1], 2)
        out[field.name] = _decode(field, raw)
    return out


def _encode(field, value):
    width = field.width
    if field.kind == "f":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise BitfieldError("字段 %s 的值应为数值：%r" % (field.name, value))
        scaled = float(value) * (1 << field.frac)
        raw = int(scaled + 0.5) if scaled >= 0 else -int(-scaled + 0.5)
    else:
        if isinstance(value, bool) or not isinstance(value, int):
            raise BitfieldError("字段 %s 的值应为整数：%r" % (field.name, value))
        raw = value
    if field.kind == "s":
        low, high = -(1 << (width - 1)), (1 << (width - 1)) - 1
    else:
        low, high = 0, (1 << width) - 1
    if not low <= raw <= high:
        raise BitfieldError(
            "字段 %s 的值 %r 超出 %d 位范围（%d 到 %d）"
            % (field.name, value, width, low, high)
        )
    return raw & ((1 << width) - 1)


def pack(values, fields, order="msb"):
    _validate(fields)
    by_name = {field.name: field for field in fields}
    for name in values:
        if name not in by_name:
            raise BitfieldError("打包值里有未定义的字段：%s" % name)
    total_bits = max(field.offset + field.width for field in fields)
    bits = ["0"] * total_bits
    for field in fields:
        raw = _encode(field, values.get(field.name, 0))
        chunk = format(raw, "0%db" % field.width)
        if order == "msb":
            bits[field.offset:field.offset + field.width] = chunk
        elif order == "lsb":
            bits[field.offset:field.offset + field.width] = chunk[::-1]
        else:
            raise BitfieldError("位序应为 msb 或 lsb：%r" % order)
    out = bytearray()
    for start in range(0, total_bits, 8):
        byte_bits = "".join(bits[start:start + 8]).ljust(8, "0")
        if order == "lsb":
            byte_bits = byte_bits[::-1]
        out.append(int(byte_bits, 2))
    return bytes(out)
