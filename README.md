# bitfield

按字段定义把字节串解包成整数，也支持反向打包，只用 Python 标准库。

```
python3 -m bitfield.cli --hex F0 --fields "a:0:4:s"
python3 -m bitfield.cli --hex F0 --fields "b:0:8"
python3 -m bitfield.cli --hex 01 --fields "x:0:8" --order lsb
python3 -m bitfield.cli --hex F0 --fields "d:0:8:f" --frac 4
python3 -m bitfield.cli --fields "a:0:4:s,b:4:4" --pack "a=-1,b=3"
python3 -m unittest discover -s tests -v
```

## 口径（README 为准）

- 位序默认是**大端位序**（`--order msb`）：offset 0 是第一个字节的最高位，字段按位从左往右排。
  `--order lsb` 时按 LSB0 解释：位 0 是第一个字节的最低有效位。
- **有符号字段按二进制补码还原**：4 位 `1111` 是 `-1`、`1000` 是 `-8`。
- 字段类型：`u` 无符号（默认，可省略）、`s` 补码有符号、`f` 定点小数
  （按补码解释后再除以 `2^--frac`，`--frac` 默认 0）。
- **越界要报错**：字段范围超出数据长度（例如只有 1 字节却读 `offset=12, width=8`）报
  「字段 c 越界（需要 20 位，只有 8 位）」。
- **重叠要报错**：同一份字段表里两个字段覆盖同一位，报错并指出冲突的两个字段名。
- 字段定义是 `name:offset:width[:u|s|f]`；非法定义（缺段、非数字、负偏移、宽度 < 1、未知类型）
  要报错并指出字段。
- 不变量：无符号字段的值等于该位段的二进制值；有符号字段等于补码解释；
  `0 <= offset`、`width >= 1`、`offset+width <= len(data)*8` 对每个字段都成立。
- 规模：10 万个字段、1 MB 数据时 unpack 与 pack 都线性完成，内存 O(字段数 + 输出字节)，
  不把整串转成 0101 字符串再切片。

## 反向打包

`--pack "name=值,…"` 按字段定义把值写回字节串，输出十六进制；`--hex` 与 `--pack` 二选一。
值超出字段位宽要报错。往返不变量：`unpack(pack(values)) == values`
（含补码负数与定点小数，定点误差 < 1/2^frac）。

## 参数

```
--fields 定义    逗号分隔的 name:offset:width[:u|s|f]
--hex 数据       十六进制输入（解包模式）
--pack 赋值      逗号分隔的 name=值（打包模式，输出十六进制）
--order 位序     msb（默认）或 lsb
--frac N         f 类型的分数位数（除以 2^N），默认 0
```

## 输出

解包：

```
{"a": -1, "b": 240}
```

打包：

```
f3
```

## 目录

```
bitfield/unpack.py     字段解析、解包与打包
bitfield/cli.py        命令行入口
tests/reference.py     参考实现（0101 字符串切片 / 按位写回），供对照测试
tests/                 unittest 用例（含 1 万组随机对照）
```
