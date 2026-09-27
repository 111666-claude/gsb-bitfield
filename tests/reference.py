"""参考实现：正向把数据转成 0101 字符串再切片解释，反向按位写回。

刻意用直接但慢的做法，与 bitfield.unpack 的快速实现互相印证。
"""

from bitfield.unpack import BitfieldError


def _bit_string(data, order):
    chars = []
    for byte in data:
        if order == "msb":
            chars.extend("1" if byte & (0x80 >> i) else "0" for i in range(8))
        else:
            chars.extend("1" if byte & (1 << i) else "0" for i in range(8))
    return "".join(chars)


def _check_overlap(fields):
    for i in range(len(fields)):
        for j in range(i + 1, len(fields)):
            first, second = fields[i], fields[j]
            if first.offset < second.offset + second.width and second.offset < first.offset + first.width:
                raise BitfieldError("字段 %s 与字段 %s 重叠" % (first.name, second.name))


def _convert(raw, field, frac):
    if field.ftype == "u":
        return raw
    if raw >> (field.width - 1):
        raw -= 1 << field.width
    if field.ftype == "f" and frac:
        return raw / (1 << frac)
    return raw


def ref_unpack(data, fields, order="msb", frac=0):
    _check_overlap(fields)
    bits = _bit_string(data, order)
    total = len(bits)
    out = {}
    for field in fields:
        if field.offset + field.width > total:
            raise BitfieldError(
                "字段 %s 越界（需要 %d 位，只有 %d 位）" % (field.name, field.offset + field.width, total)
            )
        segment = bits[field.offset:field.offset + field.width]
        raw = int(segment, 2) if order == "msb" else int(segment[::-1], 2)
        out[field.name] = _convert(raw, field, frac)
    return out


def _encode(field, value, frac):
    mask = (1 << field.width) - 1
    if field.ftype == "f":
        scaled = int(round(value * (1 << frac)))
        if not -(1 << (field.width - 1)) <= scaled <= (1 << (field.width - 1)) - 1:
            raise BitfieldError("字段 %s 的值 %r 超出 %d 位范围" % (field.name, value, field.width))
        return scaled & mask
    if field.ftype == "s":
        if not -(1 << (field.width - 1)) <= value <= (1 << (field.width - 1)) - 1:
            raise BitfieldError("字段 %s 的值 %r 超出 %d 位范围" % (field.name, value, field.width))
        return value & mask
    if not 0 <= value <= mask:
        raise BitfieldError("字段 %s 的值 %r 超出 %d 位范围" % (field.name, value, field.width))
    return value


def ref_pack(fields, values, order="msb", frac=0):
    _check_overlap(fields)
    total = max((field.offset + field.width for field in fields), default=0)
    bits = ["0"] * (((total + 7) // 8) * 8)
    for field in fields:
        raw = _encode(field, values[field.name], frac)
        for k in range(field.width):
            bit = (raw >> (field.width - 1 - k)) & 1 if order == "msb" else (raw >> k) & 1
            bits[field.offset + k] = "1" if bit else "0"
    out = bytearray()
    for start in range(0, len(bits), 8):
        chunk = bits[start:start + 8]
        out.append(int("".join(chunk), 2) if order == "msb" else int("".join(chunk[::-1]), 2))
    return bytes(out)
