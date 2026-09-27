"""按位域解包/打包字节串。只用标准库。"""

ORDERS = ("msb", "lsb")
KINDS = ("u", "s", "f")


class BitfieldError(Exception):
    """位域定义、数据或取值有问题。"""

    def __init__(self, message):
        super().__init__(message)
        self.message = message


class Field:
    def __init__(self, name, offset, width, kind="u", frac=None):
        self.name = name
        self.offset = offset
        self.width = width
        self.kind = kind
        self.frac = frac if frac is not None else 0

    @property
    def signed(self):
        return self.kind == "s"


def _parse_int(text, spec, what):
    try:
        return int(text)
    except ValueError:
        raise BitfieldError("字段 %s 应该是整数（%s）：%r" % (what, spec, text))


def parse_field(spec, default_frac=0):
    """解析 `name:offset:width[:kind[:frac]]`，kind 是 u/s/f。"""
    parts = spec.split(":")
    if len(parts) not in (3, 4, 5):
        raise BitfieldError("字段格式应该是 name:offset:width[:kind[:frac]]：%r" % spec)
    name = parts[0].strip()
    if not name:
        raise BitfieldError("字段名不能为空：%r" % spec)
    offset = _parse_int(parts[1], spec, "偏移量")
    width = _parse_int(parts[2], spec, "位宽")
    if offset < 0:
        raise BitfieldError("字段 %s 偏移量不能为负：%d" % (name, offset))
    if width < 1:
        raise BitfieldError("字段 %s 位宽至少为 1：%d" % (name, width))
    kind = "u"
    if len(parts) >= 4 and parts[3]:
        kind = parts[3]
        if kind not in KINDS:
            raise BitfieldError("字段 %s 类型应为 u/s/f：%r" % (name, kind))
    frac = default_frac if kind == "f" else 0
    if len(parts) == 5 and parts[4]:
        frac = _parse_int(parts[4], spec, "定点小数位数")
        if frac < 0:
            raise BitfieldError("字段 %s 定点小数位数不能为负：%d" % (name, frac))
    return Field(name, offset, width, kind, frac)


def _check_definitions(fields):
    if not fields:
        raise BitfieldError("字段表为空")
    seen = set()
    for field in fields:
        if not field.name:
            raise BitfieldError("字段名不能为空")
        if field.name in seen:
            raise BitfieldError("字段名重复：%s" % field.name)
        seen.add(field.name)
        if not isinstance(field.offset, int) or field.offset < 0:
            raise BitfieldError("字段 %s 偏移量必须为非负整数" % field.name)
        if not isinstance(field.width, int) or field.width < 1:
            raise BitfieldError("字段 %s 位宽必须 >= 1" % field.name)
        if field.kind not in KINDS:
            raise BitfieldError("字段 %s 类型应为 u/s/f：%r" % (field.name, field.kind))
        if not isinstance(field.frac, int) or field.frac < 0:
            raise BitfieldError("字段 %s 定点小数位数必须为非负整数" % field.name)


def _check_bounds(fields, total_bits):
    for field in fields:
        end = field.offset + field.width
        if end > total_bits:
            raise BitfieldError(
                "字段 %s 越界（需要 %d 位，只有 %d 位）"
                % (field.name, end, total_bits)
            )


def _find_owner(fields, bit):
    for field in fields:
        if field.offset <= bit < field.offset + field.width:
            return field
    return None


def _check_overlaps(fields):
    """用按位打包的覆盖表线性扫描；命中后再定位冲突字段。"""
    total_bits = max(field.offset + field.width for field in fields)
    words = [0] * ((total_bits + 63) >> 6)
    for field in fields:
        start = field.offset
        stop = field.offset + field.width
        wi = start >> 6
        bit_in_word = start & 63
        remaining = field.width
        if bit_in_word:
            take = min(remaining, 64 - bit_in_word)
            mask = ((1 << take) - 1) << bit_in_word
            if words[wi] & mask:
                other = _find_owner(fields, start)
                raise BitfieldError("字段 %s 与 %s 覆盖位重叠" % (field.name, other.name))
            words[wi] |= mask
            remaining -= take
            wi += 1
        while remaining >= 64:
            if words[wi]:
                hit = words[wi] & -words[wi]
                other = _find_owner(fields, (wi << 6) | hit.bit_length() - 1)
                raise BitfieldError("字段 %s 与 %s 覆盖位重叠" % (field.name, other.name))
            words[wi] = ~0
            remaining -= 64
            wi += 1
        if remaining:
            mask = (1 << remaining) - 1
            if words[wi] & mask:
                other = _find_owner(fields, wi << 6)
                raise BitfieldError("字段 %s 与 %s 覆盖位重叠" % (field.name, other.name))
            words[wi] |= mask


def _extract_msb(data, offset, width):
    """MSB0：offset 0 是首字节最高位。逐对齐机器字读取，O(width/8)。"""
    value = 0
    bitpos = offset
    remaining = width
    while remaining:
        byte_index = bitpos >> 3
        bit_in_byte = bitpos & 7
        avail = min(remaining, 8 - bit_in_byte)
        chunk = (data[byte_index] << (bit_in_byte + 24)) & 0xFFFFFFFF
        chunk >>= 32 - avail
        value = (value << avail) | chunk
        bitpos += avail
        remaining -= avail
    return value


def _extract_lsb(data, offset, width):
    """LSB0：位 0 是首字节最低有效位。"""
    value = 0
    out_pos = 0
    bitpos = offset
    remaining = width
    while remaining:
        byte_index = bitpos >> 3
        bit_in_byte = bitpos & 7
        avail = min(remaining, 8 - bit_in_byte)
        chunk = data[byte_index] >> bit_in_byte
        if avail < 8:
            chunk &= (1 << avail) - 1
        value |= chunk << out_pos
        out_pos += avail
        bitpos += avail
        remaining -= avail
    return value


def _decode(field, raw):
    if field.kind == "s" and raw >> (field.width - 1):
        return raw - (1 << field.width)
    if field.kind == "f":
        return raw / (1 << field.frac)
    return raw


def unpack(data, fields, order="msb"):
    """把字节串解包成 {字段名: 值}。时间 O(字段总位宽/8 + 输出)。"""
    if order not in ORDERS:
        raise BitfieldError("位序应为 msb 或 lsb：%r" % order)
    _check_definitions(fields)
    total_bits = len(data) * 8
    _check_bounds(fields, total_bits)
    _check_overlaps(fields)
    extract = _extract_msb if order == "msb" else _extract_lsb
    return {
        field.name: _decode(field, extract(data, field.offset, field.width))
        for field in fields
    }


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
    low, high = (-(1 << (width - 1)), (1 << (width - 1)) - 1) if field.kind == "s" else (0, (1 << width) - 1)
    if not low <= raw <= high:
        raise BitfieldError(
            "字段 %s 的值 %r 超出 %d 位范围（%d 到 %d）"
            % (field.name, value, width, low, high)
        )
    return raw & ((1 << width) - 1)


def _insert_msb(buf, offset, width, raw):
    bitpos = offset
    remaining = width
    while remaining:
        byte_index = bitpos >> 3
        bit_in_byte = bitpos & 7
        avail = min(remaining, 8 - bit_in_byte)
        chunk = (raw >> (remaining - avail)) & ((1 << avail) - 1)
        buf[byte_index] |= chunk << (8 - bit_in_byte - avail)
        bitpos += avail
        remaining -= avail


def _insert_lsb(buf, offset, width, raw):
    bitpos = offset
    in_pos = 0
    remaining = width
    while remaining:
        byte_index = bitpos >> 3
        bit_in_byte = bitpos & 7
        avail = min(remaining, 8 - bit_in_byte)
        chunk = (raw >> in_pos) & ((1 << avail) - 1)
        buf[byte_index] |= chunk << bit_in_byte
        in_pos += avail
        bitpos += avail
        remaining -= avail


def pack(values, fields, order="msb"):
    """按字段定义把值写回字节串（未覆盖字节为 0）。"""
    if order not in ORDERS:
        raise BitfieldError("位序应为 msb 或 lsb：%r" % order)
    _check_definitions(fields)
    _check_overlaps(fields)
    by_name = {field.name: field for field in fields}
    for name in values:
        if name not in by_name:
            raise BitfieldError("打包值里有未定义的字段：%s" % name)
    total_bytes = (max(field.offset + field.width for field in fields) + 7) >> 3
    buf = bytearray(total_bytes)
    insert = _insert_msb if order == "msb" else _insert_lsb
    for field in fields:
        insert(buf, field.offset, field.width, _encode(field, values.get(field.name, 0)))
    return bytes(buf)
