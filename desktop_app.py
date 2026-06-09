#!/usr/bin/env python3
import json
import sys
import traceback
from pathlib import Path
from tkinter import Button, Entry, Label, StringVar, Tk, filedialog, messagebox

import pandas as pd

from build_workbook import build_workbook
from exchange_rates import fetch_ecb_rates_to_eur
from run_workflow import build_payload, clean_json_value


APP_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = Path.home() / "Desktop" / "A1-A3税务工作流输出"


def resource_path(name):
    bundled_dir = getattr(sys, "_MEIPASS", None)
    if bundled_dir:
        return Path(bundled_dir) / name
    return APP_DIR / name


def config_path():
    external_config = APP_DIR / "config.json"
    if external_config.exists():
        return external_config
    return resource_path("config.json")


class TaxWorkflowApp:
    def __init__(self):
        self.root = Tk()
        self.root.title("A1-A3未代扣代缴自动工作流")
        self.root.geometry("720x360")
        self.csv_path = StringVar()
        self.month = StringVar(value="2026-MAR")
        self.pln = StringVar()
        self.sek = StringVar(value="0.0928")
        self.gbp = StringVar()
        self.rate_source = StringVar(value="手动填写")
        self.status = StringVar(value="请选择 CSV 文件，填写月份和汇率。")
        self._build_ui()

    def _build_ui(self):
        Label(self.root, text="Amazon VAT CSV 文件").grid(row=0, column=0, padx=16, pady=14, sticky="w")
        Entry(self.root, textvariable=self.csv_path, width=68).grid(row=0, column=1, padx=8, pady=14, sticky="we")
        Button(self.root, text="选择文件", command=self.choose_file).grid(row=0, column=2, padx=16, pady=14)

        Label(self.root, text="算税月").grid(row=1, column=0, padx=16, pady=8, sticky="w")
        Entry(self.root, textvariable=self.month, width=24).grid(row=1, column=1, padx=8, pady=8, sticky="w")

        Label(self.root, text="PLN 汇率").grid(row=2, column=0, padx=16, pady=8, sticky="w")
        Entry(self.root, textvariable=self.pln, width=24).grid(row=2, column=1, padx=8, pady=8, sticky="w")

        Label(self.root, text="SEK 汇率").grid(row=3, column=0, padx=16, pady=8, sticky="w")
        Entry(self.root, textvariable=self.sek, width=24).grid(row=3, column=1, padx=8, pady=8, sticky="w")

        Label(self.root, text="GBP 汇率").grid(row=4, column=0, padx=16, pady=8, sticky="w")
        Entry(self.root, textvariable=self.gbp, width=24).grid(row=4, column=1, padx=8, pady=8, sticky="w")

        Button(self.root, text="自动获取 ECB 汇率", command=self.fetch_rates).grid(row=5, column=1, padx=8, pady=8, sticky="w")
        Label(self.root, textvariable=self.rate_source).grid(row=5, column=1, padx=160, pady=8, sticky="w")

        Button(self.root, text="生成结果", command=self.run).grid(row=6, column=1, padx=8, pady=18, sticky="w")
        Label(self.root, textvariable=self.status, wraplength=640, justify="left").grid(row=7, column=0, columnspan=3, padx=16, pady=10, sticky="w")
        self.root.columnconfigure(1, weight=1)

    def choose_file(self):
        path = filedialog.askopenfilename(filetypes=[("CSV 文件", "*.csv"), ("所有文件", "*.*")])
        if path:
            self.csv_path.set(path)

    def _rate_value(self, value):
        value = value.strip()
        if not value:
            return None
        return float(value)

    def fetch_rates(self):
        try:
            self.status.set("正在从 ECB 获取汇率...")
            self.root.update_idletasks()
            data = fetch_ecb_rates_to_eur()
            rates = data["rates"]
            self.pln.set(str(rates["PLN"]))
            self.sek.set(str(rates["SEK"]))
            self.gbp.set(str(rates["GBP"]))
            source = f'ECB {data["date"]}'
            self.rate_source.set(f"汇率来源：{source}")
            self.status.set(f"已自动填入 {source} 汇率，可按申报口径手动修改。")
        except Exception as error:
            self.rate_source.set("汇率来源：手动填写")
            messagebox.showerror("获取汇率失败", f"无法自动获取 ECB 汇率，请手动填写。\n\n{error}")

    def run(self):
        try:
            input_file = Path(self.csv_path.get())
            month = self.month.get().strip()
            if not input_file.exists():
                messagebox.showerror("缺少文件", "请先选择 Amazon VAT CSV 文件。")
                return
            if not month:
                messagebox.showerror("缺少月份", "请填写算税月，例如 2026-MAR。")
                return

            config = json.loads(config_path().read_text(encoding="utf-8"))
            config["exchange_rates_to_eur"][month] = {
                "EUR": 1,
                "PLN": self._rate_value(self.pln.get()),
                "SEK": self._rate_value(self.sek.get()),
                "GBP": self._rate_value(self.gbp.get()),
            }
            config["exchange_rate_source"] = self.rate_source.get()

            out_dir = DEFAULT_OUTPUT_DIR / month
            out_dir.mkdir(parents=True, exist_ok=True)
            payload = clean_json_value(build_payload(input_file, month, config))
            (out_dir / "workflow_result.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str, allow_nan=False), encoding="utf-8")
            pd.DataFrame(payload["summary"]).to_csv(out_dir / "A1-A3汇总.csv", index=False, encoding="utf-8-sig")
            pd.DataFrame(payload["currency"]).to_csv(out_dir / "币种汇总.csv", index=False, encoding="utf-8-sig")
            pd.DataFrame(payload["final"]).to_csv(out_dir / "最终税金.csv", index=False, encoding="utf-8-sig")
            pd.DataFrame(payload["detail"]).to_csv(out_dir / "命中明细.csv", index=False, encoding="utf-8-sig")

            xlsx_path = build_workbook(payload, out_dir / f"A1-A3未代扣代缴输出_{month}.xlsx")
            self.status.set(f"完成：{xlsx_path}")
            messagebox.showinfo("生成完成", f"结果已生成：\n{xlsx_path}")
        except Exception as error:
            traceback.print_exc()
            messagebox.showerror("生成失败", str(error))

    def mainloop(self):
        self.root.mainloop()


if __name__ == "__main__":
    TaxWorkflowApp().mainloop()
