"""命令行入口：按字段定义解包十六进制数据，或反向打包。"""

import argparse
import json
import sys

from .unpack import BitfieldError, pack, parse_field, unpack


def build_parser():
    parser = argparse.ArgumentParser(prog="bitfield", description="位域解包/打包")
    parser.add_argument("--hex", help="十六进制数据")
    parser.add_argument("--fields", required=True, help="逗号分隔的 name:offset:width[:u|s|f]")
    parser.add_argument("--order", choices=("msb", "lsb"), default="msb",
                        help="位序：msb 大端位序（默认），lsb 按 LSB0 解释")
    parser.add_argument("--frac", type=int, default=0, help="f 类型定点小数的分数位数（除以 2^N）")
    parser.add_argument("--pack", help='反向打包，形如 "name=值,…"，输出十六进制')
    return parser


def _parse_assignments(text, fields):
    by_name = {field.name: field for field in fields}
    values = {}
    for item in text.split(","):
        item = item.strip()
        if not item:
            continue
        name, sep, raw = item.partition("=")
        if not sep:
            raise BitfieldError("打包项应该是 name=值：%r" % item)
        field = by_name.get(name.strip())
        if field is None:
            raise BitfieldError("打包值没有对应字段：%r" % name.strip())
        values[field.name] = float(raw) if field.ftype == "f" else int(raw)
    return values


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.frac < 0:
        print("错误：--frac 不能为负", file=sys.stderr)
        return 2
    try:
        fields = [parse_field(spec.strip()) for spec in args.fields.split(",") if spec.strip()]
    except BitfieldError as error:
        print("错误：%s" % error, file=sys.stderr)
        return 2
    if args.pack is not None:
        if args.hex is not None:
            print("错误：--pack 与 --hex 只能二选一", file=sys.stderr)
            return 2
        try:
            values = _parse_assignments(args.pack, fields)
            packed = pack(fields, values, order=args.order, frac=args.frac)
        except (ValueError, BitfieldError) as error:
            print("错误：%s" % error, file=sys.stderr)
            return 1
        print(packed.hex())
        return 0
    if args.hex is None:
        print("错误：需要 --hex 或 --pack", file=sys.stderr)
        return 2
    try:
        data = bytes.fromhex(args.hex)
    except ValueError as error:
        print("错误：%s" % error, file=sys.stderr)
        return 2
    try:
        values = unpack(data, fields, order=args.order, frac=args.frac)
    except BitfieldError as error:
        print("错误：%s" % error, file=sys.stderr)
        return 1
    print(json.dumps(values, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
