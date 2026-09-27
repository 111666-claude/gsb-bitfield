# bitfield

按字段定义把字节串解包成数值，或按同一份字段定义反向打包，只用 Python 标准库。

```
python3 -m bitfield.cli --hex F0 --fields "a:0:4:s"          # {"a": -1}
python3 -m bitfield.cli --hex 0F --fields "a:0:4:s" --order lsb   # {"a": -1}
python3 -m bitfield.cli --hex F0 --fields "b:0:8"            # {"b": 240}
python3 -m bitfield.cli --hex 03 --fields "x:0:8:f" --frac 4 # {"x": 0.1875}
python3 -m bitfield.cli --fields "a:0:4:s,b:4:4" --pack "a=-1,b=3"  # f3
python3 -m unittest discover -s tests -v
```

## 口径（README 为准）

- 位序默认是**大端位序（MSB0）**：offset 0 是第一个字节的最高位，字段按位从左往右排。
  加 `--order lsb` 按 LSB0 解释：位 0 是首字节的最低有效位。
  注意 `--hex 0F --fields "a:0:4:s"` 在默认位序下读到的是高 4 位 `0000`（得 `0`）；
  低 4 位的 `1111` 要写 `a:4:4:s`，或加 `--order lsb`。
- **有符号字段按二进制补码还原**：4 位 `1111` 是 `-1`、`1000` 是 `-8`。
- **越界要报错**：字段范围超出数据长度（例如只有 1 字节却读 `offset=12, width=8`）报
  「字段 c 越界（需要 20 位，只有 8 位）」。
- **重叠要报错**：同一份字段表里两个字段覆盖同一位，报错并指出冲突的两个字段名。
- 字段定义是 `name:offset:width[:kind[:frac]]`：
  - `kind` 为 `u`（无符号，默认）、`s`（补码有符号）、`f`（定点小数，值 = 原始整数 / 2^frac）。
  - `frac` 可写在字段定义第 5 段，也可用 `--frac N` 给所有 `f` 字段设默认小数位数。
  - 非法定义（缺段、非数字、负偏移、宽度 < 1、未知类型）要报错并指出字段。
- **反向打包**：`--pack "name=值,..."` 按字段定义写回字节串，输出十六进制；
  值超出字段位宽要报错；未给出的字段按 0 写。往返不变量
  `unpack(pack(values)) == values`（含补码负数与定点小数，误差 < 1/2^frac）。
- 不变量：无符号字段的值等于该位段的二进制值；有符号字段等于补码解释；
  `0 <= offset`、`width >= 1`、`offset+width <= len(data)*8` 对每个字段都成立。
- 规模：10 万个字段、1 MB 数据时 unpack 与 pack 都线性完成，
  内存 O(字段数 + 输出字节)，不把整串转成 0101 字符串再切片。

## 参数

```
--fields 定义    逗号分隔的 name:offset:width[:u|s|f[:frac]]
--hex 数据       十六进制输入（解包模式）
--pack 值        反向打包：name=值,...，输出十六进制（与 --hex 二选一）
--order 位序     msb（默认）或 lsb
--frac N         f 定点字段的默认小数位数
```

## 输出

解包输出 JSON（键排序）：

```
{"a": -1, "b": 240}
```

打包输出十六进制字节串：

```
f3
```

## 目录

```
bitfield/unpack.py     字段解析、解包与打包（快速实现，按机器字线性扫描）
bitfield/cli.py        命令行入口
tests/reference.py     参考实现（正向转 0101 字符串切片、反向按位写回）
tests/test_features.py 补码、位序、定点、越界、重叠、打包的固定用例
tests/test_reference_diff.py  与参考实现的随机对照（1 万组数据 + 字段表）
tests/test_scale.py    10 万字段 / 1 MB 数据的线性与往返不变量
```
