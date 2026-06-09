# 未代扣代缴 A1-A3 自动工作流

这是一个可以本地安装使用的小工具。安装后打开桌面图标，选择 Amazon VAT CSV 文件，填写算税月和当月汇率，就会自动生成 A1-A3 汇总、税金、命中明细和 Excel 文件。

以后使用时，只需要提供三样东西：

1. Amazon VAT CSV 文件
2. 算税月，例如 `2026-MAR`
3. 当月汇率，填在 `config.json` 的 `exchange_rates_to_eur` 中

## 固定规则

每个部分都会先清空筛选，并从原始 CSV 重新开始。

通用前置筛选：

- B列 `ACTIVITY_PERIOD` = 指定算税月

### A1

- CQ列 `TAX_COLLECTION_RESPONSIBILITY` = `SELLER`
- F列 `TRANSACTION_TYPE` 非 `COMMINGLING_BUY`
- CJ列 `EXPORT_OUTSIDE_EU` = `NO + 空白`
- BP列 `SALE_DEPART_COUNTRY` = 欧盟国家
- BQ列 `SALE_ARRIVAL_COUNTRY` = 算税国家，默认 `IT`
- CA列 `BUYER_VAT_NUMBER` = 空白
- BB列 `TRANSACTION_CURRENCY_CODE` = `EUR / PLN / SEK`
- 汇总 BA列 `TOTAL_ACTIVITY_VALUE_AMT_VAT_INCL`

### A2

- CQ列 `TAX_COLLECTION_RESPONSIBILITY` = `SELLER`
- F列 `TRANSACTION_TYPE` 非 `COMMINGLING_BUY`
- CJ列 `EXPORT_OUTSIDE_EU` = `NO + 空白`
- BP列 `SALE_DEPART_COUNTRY` = 算税国家，默认 `IT`
- BQ列 `SALE_ARRIVAL_COUNTRY` = 客户没有注册税号的欧盟国家
- CA列 `BUYER_VAT_NUMBER` = 空白
- BB列 `TRANSACTION_CURRENCY_CODE` = `EUR / PLN / SEK`
- 汇总 BA列 `TOTAL_ACTIVITY_VALUE_AMT_VAT_INCL`

### A3

- CQ列 `TAX_COLLECTION_RESPONSIBILITY` = `SELLER`
- F列 `TRANSACTION_TYPE` 非 `COMMINGLING_BUY`
- CJ列 `EXPORT_OUTSIDE_EU` = `NO + 空白`
- AE列 `PRICE_OF_ITEMS_VAT_RATE_PERCENT` > `0`
- BP列 `SALE_DEPART_COUNTRY` = 算税国家，默认 `IT`
- BQ列 `SALE_ARRIVAL_COUNTRY` = 算税国家之外的欧盟国家
- CA列 `BUYER_VAT_NUMBER` = 非空白，且跨境 VAT 格式不符合要求
- BB列 `TRANSACTION_CURRENCY_CODE` = `EUR / PLN / SEK / GBP`
- 汇总 BA列 `TOTAL_ACTIVITY_VALUE_AMT_VAT_INCL`

## 最终输出

- A1、A2、A3 各自的命中行数和 EUR 金额总和
- A1-A3 命中 EUR 总和
- 税金 = `命中EUR总和 / 1.22 * 0.22`
- 命中明细
- 币种汇总

## 普通用户使用方式

安装完成后：

1. 双击桌面图标 `A1-A3税务工作流`
2. 选择 Amazon VAT CSV 文件
3. 填写算税月，例如 `2026-MAR`
4. 可以点击“自动获取 ECB 汇率”，也可以手动填写 PLN、SEK、GBP 对 EUR 汇率；没有命中的币种可以不填
5. 如申报口径和 ECB 汇率不同，可以手动修改汇率
6. 点击“生成结果”

结果会输出到：

```text
桌面/A1-A3税务工作流输出/算税月/
```

里面包含：

- `A1-A3未代扣代缴输出_算税月.xlsx`
- `A1-A3汇总.csv`
- `币种汇总.csv`
- `最终税金.csv`
- `命中明细.csv`
- `workflow_result.json`

自动获取汇率时，工具会读取 ECB 的 EUR 参考汇率，并自动换算成外币对 EUR 的汇率。

## 制作 Windows 安装包

需要在 Windows 电脑上制作安装包。

准备一次即可：

1. 安装 Python 3
2. 安装 Inno Setup 6
3. 双击运行：

```text
packaging/build_windows_installer_simple.bat
```

也可以在 PowerShell 里执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\build_windows_installer.ps1
```

生成位置：

```text
dist/installer/A1-A3税务工作流安装包.exe
```

把这个 `.exe` 发给别人安装即可。安装后会有桌面图标。

## 云端自动生成 Windows 安装包

如果当前电脑是 Mac，也可以把 `tax_workflow_tool` 文件夹上传到 GitHub 仓库，然后在 GitHub Actions 里运行 `Build Windows Installer`。

运行完成后，在 Actions 的 Artifacts 里下载：

```text
A1-A3-tax-workflow-windows-installer
```

里面就是 Windows 10 64位可用的安装包 `.exe`。

## 开发/命令行运行方式

第一次运行前安装依赖：

```bash
python3 -m pip install -r tax_workflow_tool/requirements.txt
```

```bash
python3 tax_workflow_tool/run_workflow.py --input "文件路径.csv" --month "2026-MAR"
```

如果 PLN、SEK、GBP 在某个月份有命中，但 `config.json` 里没有对应汇率，输出会标注“缺少汇率行数”，不会强行折算。
