#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Валидатор данных викторины «Битва умов».

Запуск:  python3 build/validate.py [--strict]

Коды выхода:
  0 — всё чисто (или только WARN при --strict=false)
  1 — есть FAIL
  2 — файл данных не найден / не разбирается
"""
import json
import os
import re
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "quiz_data.json")

LETTERS = "АБВГ"
TIERS = [100, 200, 300, 400, 500]
CJK = re.compile(r"[一-鿿　-〿＀-￯]")
# Ранг «сложности» по номиналу: насколько вопрос про его категорию
TIER_NAMES = {100: "простой", 200: "средний", 300: "средний+",
              400: "сложный", 500: "очень сложный"}

errors, warns = [], []


def fail(code, msg, where=""):
    errors.append((code, msg, where))


def warn(code, msg, where=""):
    warns.append((code, msg, where))


def check_text(obj, path):
    """Проверка текстовых полей на мусор."""
    for field in ("question", "explanation"):
        val = obj.get(field, "")
        if not isinstance(val, str):
            fail("TYPE", f"поле {field} не строка", path)
            continue
        if not val.strip():
            fail("EMPTY", f"пустое поле {field}", path)
        m = CJK.search(val)
        if m:
            ctx = val[max(0, m.start() - 30):m.end() + 30]
            fail("CJK", f"CJK-артефакт в {field}: ...{ctx}...", path)
        if "**" in val:
            fail("MARKER", f"маркер ** в {field}", path)
        if re.search(r"\bheapмпnonce\b", val):
            fail("GLITCH", "глитч 'heapмпnonce' в тексте", path)
        # неразрывные пробелы и мусорные пробелы
        if " " in val:
            fail("NBSP", f"неразрывный пробел в {field}", path)


def main():
    if not os.path.exists(DATA):
        print(f"FAIL: не найден {DATA}")
        return 2
    try:
        data = json.load(open(DATA, encoding="utf-8"))
    except Exception as exc:
        print(f"FAIL: данные не разбираются: {exc}")
        return 2

    rounds = data.get("rounds", [])
    if not rounds:
        print("FAIL: нет раундов")
        return 1

    seen_questions = defaultdict(list)
    seen_answers = defaultdict(list)
    all_sentences = defaultdict(list)
    fact_counter = Counter()
    cat_letters = defaultdict(list)
    tier_lengths = defaultdict(list)
    leaks = []
    longest_count = shortest_count = total_q = 0

    for ri, rnd in enumerate(rounds, 1):
        rname = rnd.get("name", f"Раунд {ri}")
        cats = rnd.get("categories", [])
        qs = rnd.get("questions", [])

        if not cats:
            fail("STRUCT", "у раунда нет категорий", rname)
        if len(qs) != len(cats) * len(TIERS):
            fail("STRUCT",
                 f"раунд должен содержать {len(cats) * len(TIERS)} вопросов "
                 f"({len(cats)} категорий × {len(TIERS)} номиналов), а содержит {len(qs)}",
                 rname)

        for qi, q in enumerate(qs):
            qid = q.get("id", "?")
            where = f"{rname}/{qid}"

            # --- структура ---
            opts = q.get("options", [])
            ans = q.get("answer", "")
            if len(opts) != 4:
                fail("STRUCT", f"вариантов ответа {len(opts)}, ожидалось 4", where)
            if ans not in LETTERS:
                fail("ANSWER", f"ответ '{ans}' не из {LETTERS}", where)
            if not isinstance(q.get("points"), int) or q["points"] not in TIERS:
                fail("POINTS", f"номинал {q.get('points')} не из {TIERS}", where)
            # id = "R<раунд>_<категория>_<тир>" — 1.1 это категория 1, 100 баллов
            cat_idx = qi // len(TIERS)
            tier_idx = qi % len(TIERS)
            expected_id = f"R{ri}_{cat_idx + 1}_{tier_idx + 1}"
            if qid != expected_id:
                fail("ID", f"id '{qid}' не соответствует позиции (ожидалось "
                           f"'{expected_id}': раунд {ri}, категория {cat_idx + 1}, "
                           f"{TIERS[tier_idx]} баллов)", where)
            if q.get("points") != TIERS[tier_idx]:
                fail("TIER", f"номинал {q.get('points')} не соответствует тиру "
                             f"{TIERS[tier_idx]} на позиции {expected_id}", where)

            check_text(q, where)

            # --- согласованность ответа с вариантами ---
            if ans in LETTERS and len(opts) == 4:
                idx = LETTERS.index(ans)
                correct_text = opts[idx].strip()
                # ответ должен встречаться ровно в одном варианте
                hits = [i for i, o in enumerate(opts)
                        if o.strip().lower() == correct_text.lower()]
                if len(hits) != 1:
                    fail("ANSWER", f"текст ответа «{correct_text}» встречается "
                                   f"{len(hits)} раз среди вариантов", where)
                if not correct_text:
                    fail("ANSWER", "у правильного варианта пустой текст", where)

                # --- утечка ответа через длину варианта ---
                # Взвешенная метрика: если правильный ответ самый длинный,
                # но такой длины ещё k вариантов, то стратегия «бери самый
                # длинный» даёт 1/k успеха. Ожидание при случайных данных —
                # 25 % (по 1/4 на «самый длинный» и «самый короткий»).
                lens = [len(o.strip()) for o in opts]
                avg = sum(lens) / 4
                if len(set(lens)) > 1:
                    mx, mn = max(lens), min(lens)
                    n_max = lens.count(mx)
                    n_min = lens.count(mn)
                    if lens[idx] == mx:
                        longest_count += 1.0 / n_max
                        if n_max == 1:
                            leaks.append((where, lens[idx] / avg, correct_text, "длиннее"))
                    if lens[idx] == mn:
                        shortest_count += 1.0 / n_min
                        if n_min == 1:
                            leaks.append((where, lens[idx] / avg, correct_text, "короче"))
                total_q += 1
                spread = (max(lens) - min(lens)) / max(1, avg)
                if spread > 1.1:
                    warn("SPREAD",
                         f"разброс длин вариантов {spread:.0%} "
                         f"(всего {sum(lens)} симв. в 4 вариантах)", where)
                if avg and lens[idx] / avg >= 1.5:
                    leaks.append((where, lens[idx] / avg, correct_text, "длиннее"))

            # --- дубли вопросов ---
            qt = q.get("question", "").strip().lower()
            if qt:
                seen_questions[qt].append(where)

            # --- дубли по смыслу (нормализованный текст без цифр) ---
            norm = re.sub(r"[\d\s\-—«»\"'(),.]+", "", qt)
            if norm:
                seen_answers[norm].append(where)

            # --- перекос букв по категориям ---
            if 0 <= cat_idx < len(cats) and ans in LETTERS:
                cat_letters[cats[cat_idx]].append(ans)

            # --- длина пояснения ---
            expl = q.get("explanation", "")
            tier_lengths[q.get("points")].append(len(expl))
            if len(expl) < 250:
                warn("THIN", f"пояснение тонкое ({len(expl)} симв.)", where)
            for sent in re.split(r"(?<=[.!?])\s+", expl):
                s = sent.strip()
                if len(s) > 60:
                    all_sentences[s].append(where)

            # --- переиспользование фактов ---
            for pat, label in [
                (r"86\s*000", "«86 000 км»"),
                (r"85\s*500", "«85 500 км»"),
                (r"3\s*075,3", "«3 075,3 млрд ткм»"),
                (r"1\s*311,1", "«1 311,1 млн пассажиров»"),
                (r"13\s*152", "«13 152 локомотива»"),
                (r"494,5", "«494,5 км/сутки»"),
                (r"0,397", "«0,397 события/млн км»"),
                (r"88\s*800|35\s*900", "«виртуальная сцепка»"),
                (r"1\s*115,8", "«1 115,8 млн т»"),
                (r"93,5", "«93,5 млн МЦД-1»"),
                (r"137,5|253,7", "«инвестиции в ПС»"),
            ]:
                if re.search(pat, expl):
                    fact_counter[label] += 1

    # --- итоговые проверки ---
    for qt, places in seen_questions.items():
        if len(places) > 1:
            fail("DUP", f"дубль вопроса «{qt[:60]}…»: {', '.join(places)}", "rounds")
    for norm, places in seen_answers.items():
        if len(places) > 1 and len(norm) > 25:
            fail("DUP", f"дубль по смыслу: {', '.join(places)}", "rounds")

    for sent, places in all_sentences.items():
        if len(places) > 1:
            fail("REPEAT", f"предложение повторяется {len(places)}× ({', '.join(places)}): "
                           f"«{sent[:70]}…»", "rounds")

    for cat, letters in cat_letters.items():
        if len(letters) >= 10:
            cnt = Counter(letters)
            for letter, n in cnt.items():
                if n / len(letters) > 0.45:
                    fail("BIAS", f"в категории «{cat}» буква {letter} в {n} из "
                                 f"{len(letters)} вопросов ({n/len(letters):.0%})", cat)
        missing = [l for l in LETTERS if l not in cnt]
        if missing and len(letters) >= 15:
            warn("BIAS", f"в категории «{cat}» не встречаются буквы: "
                         f"{', '.join(missing)}", cat)

    # перекос букв внутри раунда
    for rnd in rounds:
        letters = [q.get("answer", "") for q in rnd.get("questions", [])]
        if len(letters) < 8:
            continue
        cnt = Counter(letters)
        for letter, n in cnt.items():
            if n / len(letters) > 0.38:
                fail("BIAS", f"в раунде «{rnd.get('name', '?')}» буква {letter} "
                             f"в {n} из {len(letters)} вопросов ({n/len(letters):.0%}); "
                             f"порог 38 %", rnd.get("name", "?"))

    if total_q:
        lp = longest_count / total_q
        if lp > 0.34:
            fail("LEAK", f"стратегия «бери самый длинный вариант» даёт {lp:.0%} "
                         f"верных ответов (случайное угадывание — 12,5 %)", "rounds")
        elif lp > 0.28:
            warn("LEAK", f"стратегия «бери самый длинный вариант» даёт {lp:.0%} "
                         f"(случайное — 12,5 %)", "rounds")
        sp = shortest_count / total_q
        if sp > 0.34:
            fail("LEAK", f"стратегия «бери самый короткий вариант» даёт {sp:.0%} "
                         f"верных ответов (случайное угадывание — 12,5 %)", "rounds")
        elif sp > 0.28:
            warn("LEAK", f"стратегия «бери самый короткий вариант» даёт {sp:.0%} "
                         f"(случайное — 12,5 %)", "rounds")
        if leaks:
            print()
            print("  Сильные случаи утечки через длину варианта:")
            for qid, ratio, txt, kind in sorted(leaks, key=lambda x: -x[1])[:12]:
                print(f"    {qid}: правильный вариант в {ratio:.2f}× {kind} среднего "
                      f"— «{txt[:44]}…»")

    for label, n in fact_counter.most_common():
        if n > 8:
            warn("FACT", f"факт {label} повторяется {n} раз", "rounds")

    for tier, lens in tier_lengths.items():
        if len(lens) >= 8:
            avg = sum(lens) / len(lens)
            print(f"  · {tier} баллов ({TIER_NAMES.get(tier,'')}): "
                  f"средняя длина пояснения {avg:.0f} симв. (n={len(lens)})")

    # --- вывод ---
    print()
    if warns:
        print(f"WARN: {len(warns)}")
        for code, msg, where in warns:
            print(f"  ⚠ [{code}] {where}: {msg}")
        print()
    if errors:
        print(f"FAIL: {len(errors)}")
        for code, msg, where in errors:
            print(f"  ✗ [{code}] {where}: {msg}")
        return 1
    print(f"OK — {total_q} вопросов, ошибок нет, предупреждений {len(warns)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
