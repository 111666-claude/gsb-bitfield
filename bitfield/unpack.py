"""按位域解包字节串。只用标准库。"""


class BitfieldError(Exception):
    """位域定义或数据有问题。缺陷：不带字段名与偏移。"""

    def __init__(self, message):
        super().__init__(message)
        self.message = message


class Field:
    def __init__(self, name, offset, width, signed=False):
        self.name = name
        self.offset = offset
        self.width = width
        self.signed = signed


def parse_field(spec):
    """解析 `name:offset:width[:s]`。"""
    parts = spec.split(":")
    if len(parts) not in (3, 4):
        raise BitfieldError("字段格式应该是 name:offset:width[:s]：%r" % spec)
    name, offset, width = parts[0], int(parts[1]), int(parts[2])
    signed = len(parts) == 4 and parts[3] == "s"
    return Field(name, offset, width, signed)


def unpack(data, fields):
    """解包。缺陷：越界字段静默取 0（不报错），有符号数少减 1。"""
    out = {}
    for field in fields:
        value = 0
        for index in range(field.width):
            bit = field.offset + index
            byte = bit // 8
            if byte >= len(data):
                continue
            if data[byte] & (0x80 >> (bit % 8)):
                value |= 1 << (field.width - 1 - index)
        if field.signed and value >> (field.width - 1):
            # 缺陷：应该是 value - (1 << width)
            value = value - ((1 << field.width) - 1)
        out[field.name] = value
    return out
