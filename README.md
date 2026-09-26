# bitfield

按字段定义把字节串解包成整数，只用 Python 标准库。

```
python3 -m bitfield.cli --hex 0F --fields "a:0:4:s"
python3 -m bitfield.cli --hex F0 --fields "b:0:8"
python3 -m unittest discover -s tests -v
```

## 口径（README 为准）

- 位序是**大端位序**：offset 0 是第一个字节的最高位，字段按位从左往右排。
- **有符号字段要按二进制补码还原**：4 位 `1111` 是 `-1`、`1000` 是 `-8`。
  现在用 `value - (2^width - 1)`，`1111` 给 `0`、`1000` 给 `-7`；按口径分别是 `-1`、`-8`。
- **越界要报错**：字段范围超出数据长度（例如只有 1 字节却读 `offset=12, width=8`）必须报
  「字段 c 越界（需要 20 位，只有 8 位）」，不许静默返回 0。
- 字段定义是 `name:offset:width[:s]`，`s` 表示有符号；非法定义（缺段、非数字、负宽度）要报错并指出字段。
- 不变量：无符号字段的值等于该位段的二进制值；有符号字段等于补码解释；
  `0 <= offset`、`width >= 1`、`offset+width <= len(data)*8` 对每个字段都成立。
- 规模：10 万个字段、1 MB 数据解包要线性完成，内存 O(字段数)。

## 现在的行为

- 有符号还原写成 `value - ((1 << width) - 1)`：`0x0F` 的 4 位字段给 `{"a": 0}`（正解是 `-1`）。
- 越界字段用 `continue` 跳过，值留在 0 且不报错：`--hex 0F --fields "c:12:8"` 给 `{"c": 0}`。
- 字段定义解析里 `int()` 出错只抛原始异常，不带字段名；负宽度也没有校验。
- 位序本身是对的（`--hex F0 --fields b:0:8` 给 240），所以问题藏在补码与越界里。

## 计划新增的能力

```
--fields 定义    逗号分隔的 name:offset:width[:s]
--hex 数据       十六进制输入
```

## 输出

```
{"a": -1, "b": 240}
```

## 目录

```
bitfield/unpack.py   字段解析与解包
bitfield/cli.py      命令行入口
tests/               unittest 用例
```
