#!/usr/bin/env python3
import json
import sys
import traceback
from pathlib import Path
from tkinter import Button, Entry, Label, StringVar, Tk, filedialog, messagebox
from tkinter.ttk import Combobox

from exchange_rates import fetch_ecb_monthly_rates_to_eur
from workflow_service import build_country_payload, write_outputs


APP_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = Path.home() / "Desktop" / "税务工作流输出"
COUNTRY_OPTIONS = {"意大利 (IT)": "IT", "波兰 (PL)": "PL"}


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
        self.root.title("欧洲税务自动工作流")
        self.root.geometry("760x430")
        self.csv_path = StringVar()
        self.country = StringVar(value="意大利 (IT)")
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

        Label(self.root, text="算税国家").grid(row=1, column=0, padx=16, pady=8, sticky="w")
        country_box = Combobox(
            self.root,
            textvariable=self.country,
            values=list(COUNTRY_OPTIONS),
            state="readonly",
            width=21,
        )
        country_box.grid(row=1, column=1, padx=8, pady=8, sticky="w")

        Label(self.root, text="算税月").grid(row=2, column=0, padx=16, pady=8, sticky="w")
        Entry(self.root, textvariable=self.month, width=24).grid(row=2, column=1, padx=8, pady=8, sticky="w")

        Label(self.root, text="PLN 对 EUR 汇率").grid(row=3, column=0, padx=16, pady=8, sticky="w")
        Entry(self.root, textvariable=self.pln, width=24).grid(row=3, column=1, padx=8, pady=8, sticky="w")

        Label(self.root, text="SEK 对 EUR 汇率").grid(row=4, column=0, padx=16, pady=8, sticky="w")
        Entry(self.root, textvariable=self.sek, width=24).grid(row=4, column=1, padx=8, pady=8, sticky="w")

        Label(self.root, text="GBP 对 EUR 汇率").grid(row=5, column=0, padx=16, pady=8, sticky="w")
        Entry(self.root, textvariable=self.gbp, width=24).grid(row=5, column=1, padx=8, pady=8, sticky="w")

        Button(self.root, text="自动获取当月 ECB 平均汇率", command=self.fetch_rates).grid(row=6, column=1, padx=8, pady=8, sticky="w")
        Label(self.root, textvariable=self.rate_source).grid(row=6, column=1, padx=230, pady=8, sticky="w")

        Button(self.root, text="生成结果", command=self.run).grid(row=7, column=1, padx=8, pady=18, sticky="w")
        Label(self.root, textvariable=self.status, wraplength=690, justify="left").grid(row=8, column=0, columnspan=3, padx=16, pady=10, sticky="w")
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
            month = self.month.get().strip()
            if not month:
                messagebox.showerror("缺少月份", "请先填写算税月，例如 2026-MAR。")
                return
            self.status.set(f"正在从 ECB 获取 {month} 月平均汇率...")
            self.root.update_idletasks()
            data = fetch_ecb_monthly_rates_to_eur(month)
            rates = data["rates"]
            self.pln.set(str(rates["PLN"]))
            self.sek.set(str(rates["SEK"]))
            self.gbp.set(str(rates["GBP"]))
            source = f'ECB月平均 {data["date_range"]}'
            self.rate_source.set(f"汇率来源：{source}")
            self.status.set(f"已自动填入 {source} 汇率，可按申报口径手动修改。")
        except Exception as error:
            self.rate_source.set("汇率来源：手动填写")
            messagebox.showerror("获取汇率失败", f"无法自动获取 ECB 汇率，请手动填写。\n\n{error}")

    def run(self):
        try:
            input_file = Path(self.csv_path.get())
            month = self.month.get().strip()
            country = COUNTRY_OPTIONS[self.country.get()]
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

            payload = build_country_payload(input_file, month, country, config)
            paths = write_outputs(payload, DEFAULT_OUTPUT_DIR)
            xlsx_path = paths["xlsx_path"]
            self.status.set(f"完成：{xlsx_path}")
            messagebox.showinfo("生成完成", f"结果已生成：\n{xlsx_path}")
        except Exception as error:
            traceback.print_exc()
            messagebox.showerror("生成失败", str(error))

    def mainloop(self):
        self.root.mainloop()


if __name__ == "__main__":
    TaxWorkflowApp().mainloop()
