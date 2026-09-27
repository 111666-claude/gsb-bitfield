"""命令行入口：按字段定义解包十六进制数据，或反向打包。"""

import argparse
import json
import sys

from .unpack import BitfieldError, parse_field, pack, unpack


def build_parser():
    parser = argparse.ArgumentParser(prog="bitfield", description="位域解包/打包")
    parser.add_argument("--hex", help="十六进制数据")
    parser.add_argument("--fields", required=True, help="逗号分隔的 name:offset:width[:u|s|f[:frac]]")
    parser.add_argument("--order", choices=("msb", "lsb"), default="msb",
                        help="位序：msb（默认，位 0 是首字节最高位）或 lsb（位 0 是最低有效位）")
    parser.add_argument("--frac", type=int, default=0,
                        help="f 定点字段默认的小数位数（值除以 2^frac）")
    parser.add_argument("--pack", help="反向打包：name=值,...，输出十六进制字节串")
    return parser


def _parse_pack_values(text):
    values = {}
    for item in text.split(","):
        item = item.strip()
        if not item:
            continue
        if "=" not in item:
            raise BitfieldError("打包项应为 name=值：%r" % item)
        name, raw = item.split("=", 1)
        name = name.strip()
        if not name:
            raise BitfieldError("打包项字段名为空：%r" % item)
        if name in values:
            raise BitfieldError("打包值重复：%s" % name)
        raw = raw.strip()
        try:
            values[name] = int(raw)
        except ValueError:
            try:
                values[name] = float(raw)
            except ValueError:
                raise BitfieldError("打包值不是数值：%r" % item)
    return values


def main(argv=None):
    args = build_parser().parse_args(argv)
    if (args.hex is None) == (args.pack is None):
        print("错误：--hex 与 --pack 必须且只能给一个", file=sys.stderr)
        return 2
    try:
        fields = [parse_field(spec.strip(), default_frac=args.frac)
                  for spec in args.fields.split(",") if spec.strip()]
    except BitfieldError as error:
        print("错误：%s" % error, file=sys.stderr)
        return 2
    if args.pack is not None:
        try:
            values = _parse_pack_values(args.pack)
        except BitfieldError as error:
            print("错误：%s" % error, file=sys.stderr)
            return 2
        try:
            data = pack(values, fields, order=args.order)
        except BitfieldError as error:
            print("错误：%s" % error, file=sys.stderr)
            return 1
        print(data.hex())
        return 0
    try:
        data = bytes.fromhex(args.hex)
    except ValueError as error:
        print("错误：%s" % error, file=sys.stderr)
        return 2
    try:
        values = unpack(data, fields, order=args.order)
    except BitfieldError as error:
        print("错误：%s" % error, file=sys.stderr)
        return 1
    print(json.dumps(values, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
