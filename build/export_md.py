#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Экспорт данных викторины в Markdown для ведущего: Раунд_1.md … Раунд_N.md.

Запуск:  python3 build/export_md.py
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(HERE, "quiz_data.json")
LETTERS = "АБВГ"


def main():
    data = json.load(open(DATA, encoding="utf-8"))
    for ri, rnd in enumerate(data["rounds"], 1):
        cats = rnd["categories"]
        md = [f"# Раунд {ri} — {rnd['name']}", ""]
        md += [f"**Категории:** {' · '.join(cats)}", ""]
        md += ["| № | Категория | Баллы |", "|---|---|---|"]
        for ci, cat in enumerate(cats):
            for ti in range(5):
                md.append(f"| {ci + 1}.{ti + 1} | {cat} | {(ti + 1) * 100} |")
        md.append("")

        for ci, cat in enumerate(cats):
            md += [f"## {cat}", ""]
            for ti in range(5):
                q = rnd["questions"][ci * 5 + ti]
                ai = LETTERS.index(q["answer"])
                md += [f"### {(ti + 1) * 100} баллов", ""]
                md += [f"**{q['question']}**", ""]
                for i, opt in enumerate(q["options"]):
                    md.append(f"- {LETTERS[i]}) {opt}")
                md += ["",
                       f"**Правильный ответ: {LETTERS[ai]}) {q['options'][ai]}**", ""]
                md += ["**Пояснение:**", ""]
                for para in q["explanation"].split("\n"):
                    if para.strip():
                        md += [para.strip(), ""]
            md += ["---", ""]

        path = os.path.join(ROOT, f"Раунд_{ri}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(md))
        print(f"OK → {os.path.basename(path)}  "
              f"({len(rnd['questions'])} вопросов, {len('\n'.join(md)) // 1024} КБ)")


if __name__ == "__main__":
    main()
