"""命令行入口：按字段定义解包十六进制数据。"""

import argparse
import json
import sys

from .unpack import BitfieldError, parse_field, unpack


def build_parser():
    parser = argparse.ArgumentParser(prog="bitfield", description="位域解包")
    parser.add_argument("--hex", required=True, help="十六进制数据")
    parser.add_argument("--fields", required=True, help="逗号分隔的 name:offset:width[:s]")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        data = bytes.fromhex(args.hex)
        fields = [parse_field(spec.strip()) for spec in args.fields.split(",") if spec.strip()]
    except (ValueError, BitfieldError) as error:
        print("错误：%s" % error, file=sys.stderr)
        return 2
    try:
        values = unpack(data, fields)
    except BitfieldError as error:
        print("错误：%s" % error, file=sys.stderr)
        return 1
    print(json.dumps(values, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
