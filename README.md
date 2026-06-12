# 欧洲税务自动工作流

本地桌面工具目前支持意大利（IT）、波兰（PL）和德国（DE）Amazon VAT CSV 计税。选择 CSV、算税国家和算税期间后，工具按对应国家的独立规则生成汇总、币种折算、税金、命中明细和 Excel。

## 使用方式

1. 选择 Amazon VAT CSV。
2. 选择算税国家：意大利、波兰或德国。
3. 选择 CSV 后，工具自动读取 B 列 `ACTIVITY_PERIOD` 并填写算税期间；意大利、波兰按月，德国按自然季度。
4. 点击“自动获取当月 ECB 平均汇率”，或手动填写 PLN、SEK、GBP 对 EUR 汇率。
5. 点击“生成结果”。

结果输出到：

```text
桌面/税务工作流输出/国家代码/算税月/
```

统一包含：

- `国家税务工作流输出_算税月.xlsx`
- `工作流汇总.csv`
- `币种汇总.csv`
- `最终税金.csv`
- `命中明细.csv`
- `workflow_result.json`

Excel 固定包含“最终输出”和“命中明细”两张工作表；“命中明细”保留完整字段，并与单独输出的 `命中明细.csv` 列顺序一致。

## 意大利规则

意大利继续使用已验证的 A1、A2、A3 工作流，税率为 22%，总税金公式为：

```text
命中EUR总和 / 1.22 * 0.22
```

## 波兰规则

波兰每个部分都从原始 CSV 重新筛选，不继承上一部分筛选。

### 1A：PL 到未注册欧盟国家 B2C 23%

- `CQ=SELLER`
- `CA=空白`
- `BP=PL`
- `BQ=未注册税号的欧盟国家`
- `BB=EUR/PLN/SEK`
- 汇总 `BA`

### 1B：欧盟国家到 PL B2C 23%

- `CQ=SELLER`
- `CA=空白`
- `BQ=PL`
- `BP=欧盟国家`
- `BB=EUR/PLN/SEK`
- 汇总 `BA`

### 2A：波兰境内 B2B 23%

- `CQ=SELLER`
- `BP=PL`
- `BQ=PL`
- `CA` 清除空格和连字符后符合 `PL+10位数字`
- `BB=EUR/PLN/SEK`
- 汇总 `BA`

### 3A：假的欧盟境内 B2B 23%

- `CQ=SELLER`
- `CA=非空`
- `BP=PL`
- `AQ=非空且不等于0`
- `BB=EUR/PLN/SEK`
- 汇总 `BA`
- 不限制 `BQ`，不考虑是否与其他部分重复

波兰总税金公式为：

```text
3A命中EUR总和 / 1.23 * 0.23
```

波兰最终“命中总和”同样只显示 3A 命中 EUR 总和；1A、1B、2A仅在分项中展示。

Excel 仅保留“最终输出”和“命中明细”两个 Sheet。“命中明细”与单独输出的 `命中明细.csv` 保持完整字段和相同列顺序。

## 德国规则

德国按自然季度计算，例如 `2026-Q1` 对应 `2026-JAN` 至 `2026-MAR`。B列仅用于验证文件是否包含完整季度，不参与四个部分的逐行筛选；每个部分都从原始 CSV 重新开始。

- A：B2C EU→DE
- B：B2C DE→没有当地增值税号的欧盟国家
- C：待确认 B2B DE→EU，CA 非空的记录均计入；税号格式看似有效的记录在 Excel 明细中标黄，留待人工确认
- D：德国本土 B2B，CA 只需自身基本格式有效，不要求德国税号

德国总税金公式为：

```text
A-D命中EUR总和 / 1.19 * 0.19
```

## 命令行运行

```bash
python3 run_country_workflow.py \
  --input "文件路径.csv" \
  --month "2026-APR" \
  --country PL \
  --ecb-monthly
```

`--country` 支持 `IT` 和 `PL`。不使用 `--ecb-monthly` 时，汇率从配置或手动输入读取。

## Windows 安装包

在 Windows 上运行：

```text
packaging/build_windows_installer_simple.bat
```

安装包输出为：

```text
dist/installer/欧洲税务工作流安装包.exe
```
