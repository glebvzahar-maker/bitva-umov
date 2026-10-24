#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сборка «Викторина_Помощник.html» из build/quiz_data.json + build/template.html.

Запуск:  python3 build/build.py
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(HERE, "quiz_data.json")
TPL = os.path.join(HERE, "template.html")
TOKENS = os.path.join(ROOT, "design-tokens.css")
OUT = os.path.join(ROOT, "Викторина_Помощник.html")


def main():
    if not os.path.exists(DATA) or not os.path.exists(TPL):
        print("FAIL: нет quiz_data.json или template.html")
        return 2

    data = json.load(open(DATA, encoding="utf-8"))
    tpl = open(TPL, encoding="utf-8").read()

    if "__ROUNDS_JSON__" not in tpl:
        print("FAIL: в шаблоне нет плейсхолдера __ROUNDS_JSON__")
        return 2

    # единый слой токенов встраиваем внутрь — викторина остаётся одним файлом
    if "__DESIGN_TOKENS__" in tpl:
        tokens = open(TOKENS, encoding="utf-8").read() if os.path.exists(TOKENS) else ""
        tpl = tpl.replace("__DESIGN_TOKENS__", tokens)

    payload = json.dumps(data["rounds"], ensure_ascii=False, separators=(",", ":"))
    # страховка от literal newlines и прочих управляющих символов внутри строк
    assert "\n" not in payload, "в JSON обнаружен перевод строки"
    html = tpl.replace("__ROUNDS_JSON__", payload)

    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)

    n = sum(len(r["questions"]) for r in data["rounds"])
    print(f"OK → {os.path.basename(OUT)}  "
          f"({len(data['rounds'])} раунда, {n} вопросов, {len(html) // 1024} КБ)")

    # автозапуск валидатора
    rc = subprocess.call([sys.executable, os.path.join(HERE, "validate.py")],
                         stdout=subprocess.DEVNULL)
    if rc == 1:
        print("ВНИМАНИЕ: валидатор нашёл ошибки (см. build/validate.py)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
