"""按位域解包/打包字节串。只用标准库。"""


class BitfieldError(Exception):
    """位域定义或数据有问题。"""

    def __init__(self, message):
        super().__init__(message)
        self.message = message


_ORDERS = ("msb", "lsb")
_TYPES = ("u", "s", "f")


class Field:
    def __init__(self, name, offset, width, ftype="u"):
        self.name = name
        self.offset = offset
        self.width = width
        self.ftype = ftype

    @property
    def signed(self):
        return self.ftype == "s"

    def __repr__(self):
        return "Field(%r, %r, %r, %r)" % (self.name, self.offset, self.width, self.ftype)


def parse_field(spec):
    """解析 `name:offset:width[:u|s|f]`，非法定义报 BitfieldError 并指出字段。"""
    parts = spec.split(":")
    if len(parts) not in (3, 4) or not parts[0]:
        raise BitfieldError("字段格式应该是 name:offset:width[:u|s|f]：%r" % spec)
    name = parts[0]
    try:
        offset = int(parts[1])
        width = int(parts[2])
    except ValueError:
        raise BitfieldError("字段 %s 的 offset/width 不是整数：%r" % (name, spec))
    if offset < 0:
        raise BitfieldError("字段 %s 的 offset 不能为负：%d" % (name, offset))
    if width < 1:
        raise BitfieldError("字段 %s 的 width 至少为 1：%d" % (name, width))
    ftype = parts[3] if len(parts) == 4 else "u"
    if ftype not in _TYPES:
        raise BitfieldError("字段 %s 的类型必须是 u/s/f：%r" % (name, ftype))
    return Field(name, offset, width, ftype)


def _check_order(order):
    if order not in _ORDERS:
        raise BitfieldError("位序必须是 msb 或 lsb：%r" % order)


def _check_overlap(fields):
    top = None
    for field in sorted(fields, key=lambda item: (item.offset, item.width)):
        if top is not None and field.offset < top.offset + top.width:
            raise BitfieldError("字段 %s 与字段 %s 重叠" % (top.name, field.name))
        if top is None or field.offset + field.width > top.offset + top.width:
            top = field


def _check_bounds(data, fields):
    total = len(data) * 8
    for field in fields:
        if field.offset + field.width > total:
            raise BitfieldError(
                "字段 %s 越界（需要 %d 位，只有 %d 位）" % (field.name, field.offset + field.width, total)
            )


def _extract(data, offset, width, order):
    start = offset // 8
    end = (offset + width - 1) // 8
    chunk = data[start:end + 1]
    if order == "msb":
        value = int.from_bytes(chunk, "big")
        shift = (end + 1) * 8 - (offset + width)
    else:
        value = int.from_bytes(chunk, "little")
        shift = offset - start * 8
    return (value >> shift) & ((1 << width) - 1)


def _convert(raw, field, frac):
    if field.ftype == "u":
        return raw
    if raw >> (field.width - 1):
        raw -= 1 << field.width
    if field.ftype == "f" and frac:
        return raw / (1 << frac)
    return raw


def unpack(data, fields, order="msb", frac=0):
    """按字段定义解包。越界、重叠、非法位序都报 BitfieldError。"""
    _check_order(order)
    _check_bounds(data, fields)
    _check_overlap(fields)
    out = {}
    for field in fields:
        out[field.name] = _convert(_extract(data, field.offset, field.width, order), field, frac)
    return out


def _encode(field, value, frac):
    mask = (1 << field.width) - 1
    if field.ftype == "f":
        scaled = int(round(value * (1 << frac)))
        low = -(1 << (field.width - 1))
        high = (1 << (field.width - 1)) - 1
        if not low <= scaled <= high:
            raise BitfieldError("字段 %s 的值 %r 超出 %d 位范围" % (field.name, value, field.width))
        return scaled & mask
    if field.ftype == "s":
        low = -(1 << (field.width - 1))
        high = (1 << (field.width - 1)) - 1
        if not isinstance(value, int) or not low <= value <= high:
            raise BitfieldError("字段 %s 的值 %r 超出 %d 位范围" % (field.name, value, field.width))
        return value & mask
    if not isinstance(value, int) or not 0 <= value <= mask:
        raise BitfieldError("字段 %s 的值 %r 超出 %d 位范围" % (field.name, value, field.width))
    return value


def _insert(data, offset, width, raw, order):
    start = offset // 8
    end = (offset + width - 1) // 8
    nbytes = end - start + 1
    mask = (1 << width) - 1
    if order == "msb":
        shift = (end + 1) * 8 - (offset + width)
        chunk = int.from_bytes(data[start:end + 1], "big")
        chunk = (chunk & ~(mask << shift)) | ((raw & mask) << shift)
        data[start:end + 1] = chunk.to_bytes(nbytes, "big")
    else:
        shift = offset - start * 8
        chunk = int.from_bytes(data[start:end + 1], "little")
        chunk = (chunk & ~(mask << shift)) | ((raw & mask) << shift)
        data[start:end + 1] = chunk.to_bytes(nbytes, "little")


def pack(fields, values, order="msb", frac=0):
    """按字段定义把值写回字节串。值超出位宽或字段重叠都报 BitfieldError。"""
    _check_order(order)
    _check_overlap(fields)
    total = 0
    for field in fields:
        if field.name not in values:
            raise BitfieldError("缺少字段 %s 的值" % field.name)
        total = max(total, field.offset + field.width)
    data = bytearray((total + 7) // 8)
    for field in fields:
        _insert(data, field.offset, field.width, _encode(field, values[field.name], frac), order)
    return bytes(data)
