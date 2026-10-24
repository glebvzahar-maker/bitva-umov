/**
 * Дымовой тест викторины: прогоняет полный сценарий ведущего.
 * Запуск:  node build/smoke_test.js
 */
const fs = require("fs");
const path = require("path");
const { JSDOM } = require("/tmp/node_modules/jsdom");

const FILE = path.join(__dirname, "..", "Викторина_Помощник.html");
const html = fs.readFileSync(FILE, "utf8");

const errors = [];
const dom = new JSDOM(html, {
  runScripts: "dangerously",
  pretendToBeVisual: true,
  url: "https://example.test/",
  beforeParse(window) {
    window.addEventListener("error", e => errors.push("window.onerror: " + e.message));
    window.confirm = () => true;
    window.prompt = () => "3321";
    window.print = () => {};
    window.URL.createObjectURL = () => "blob:mock";
    window.URL.revokeObjectURL = () => {};
  },
});
const { window } = dom;
const { document } = window;
const $ = id => document.getElementById(id);
// const/let из <script> не видны как свойства window — читаем через eval
const V = name => window.eval(name);

function check(label, cond, extra) {
  const ok = !!cond;
  console.log(`${ok ? "  ✓" : "  ✗"} ${label}${extra ? " — " + extra : ""}`);
  if (!ok) errors.push(label + (extra ? " (" + extra + ")" : ""));
  return ok;
}

function active() {
  const el = document.querySelector(".screen.active, .question-screen.active, .setup-screen.active, .choice-screen.active");
  return el ? el.id : null;
}

console.log("\n=== Дымовой тест «Битва умов» ===\n");

// ── 1. Вход по паролю ──────────────────────────────────────────────────
console.log("1. Вход");
$("lock-password").value = "1234";
window.checkPassword();
check("вход по верному паролю", active() === "screen-setup", "активный экран: " + active());
check("заголовок показан", $("app-header").style.display === "flex");

// ── 2. Неверный пароль ─────────────────────────────────────────────────
console.log("\n2. Неверный пароль");
$("lock-password").value = "0000";
window.checkPassword();
check("сообщение об ошибке", $("lock-error").textContent.includes("Неверный"));

// ── 3. Ввод названий команд ────────────────────────────────────────────
console.log("\n3. Настройка команд");
$("lock-password").value = "1234";
window.checkPassword();
["Паровоз", "Электрики", "Путевики", "Диспетчеры", "Локомотивы"].forEach((n, i) => {
  $("team-name-" + i).value = n;
});
window.finishSetup();
check("перешли к раундам", active() === "screen-rounds");
check("названия сохранены", V("TEAM_NAMES")[0] === "Паровоз" && V("TEAM_NAMES")[4] === "Локомотивы");
check("счёт обнулён", V("SCORES").every(s => s === 0));

// ── 4. Раунд и табло ────────────────────────────────────────────────────
console.log("\n4. Табло");
check("4 раунда в данных", V("ROUNDS").length === 4, "раундов: " + V("ROUNDS").length);
check("80 вопросов", V("ROUNDS").reduce((a, r) => a + r.questions.length, 0) === 80);
window.selectRound(0);
check("открылась доска", active() === "screen-board");
const cells = document.querySelectorAll("#board-grid .q-cell");
check("20 ячеек вопросов в раунде", cells.length === 20, "ячеек: " + cells.length);
const teamCells = document.querySelectorAll("#board-grid .team-cell");
check("5 ячеек команд", teamCells.length === 5);
check("в табло есть ARIA-роли", document.querySelectorAll('#board-grid [role="gridcell"]').length === 25);

// ── 5. Клик по вопросу без команды → подсказка ──────────────────────────
console.log("\n5. Подсказка при отсутствии выбора команды");
window.selectQuestion(0, 0);
check("вопрос не открылся", active() === "screen-board");
check("показана подсказка", $("toast").textContent.includes("Сначала выберите команду"),
  "текст: " + $("toast").textContent);

// ── 6. Выбор команды и открытие вопроса ────────────────────────────────
console.log("\n6. Открытие вопроса");
window.selectBoardTeam(0);
check("команда выбрана", V("selectedBoardTeam") === 0);
window.selectQuestion(0, 0);
check("вопрос открылся", active() === "screen-question");
check("бейдж содержит команду", $("q-badge").textContent.includes("Паровоз"),
  "бейдж: " + $("q-badge").textContent);
check("кнопка «Ошибка (−100)»", $("q-actions").innerHTML.includes("Ошибка (−100)"));
check("на экране нет маркера **", !$("q-body").innerHTML.includes("**"));
check("правильный ответ помечен", document.querySelectorAll("#q-body .q-option.correct").length === 1);

// ── 7. Зачёт балла ─────────────────────────────────────────────────────
console.log("\n7. Зачёт балла");
window.answerQuestion(true);
check("вернулись на табло", active() === "screen-board");
check("балл начислен", V("SCORES")[0] === 100, "счёт: " + V("SCORES")[0]);
check("ячейка помечена использованной",
  document.querySelectorAll("#board-grid .q-cell.used").length === 1);
check("кнопка Undo активна", $("undo-btn").disabled === false);
check("команда сброшена", V("selectedBoardTeam") === -1);

// ── 8. Ошибка — минус баллы ────────────────────────────────────────────
console.log("\n8. Ошибка (минус баллы)");
window.selectBoardTeam(1);
window.selectQuestion(1, 4);   // 500 баллов
window.answerQuestion(false);
check("балл снят", V("SCORES")[1] === -500, "счёт: " + V("SCORES")[1]);

// ── 9. Undo ────────────────────────────────────────────────────────────
console.log("\n9. Отмена ответа");
window.undoLastAnswer();
check("балл возвращён", V("SCORES")[1] === 0, "счёт: " + V("SCORES")[1]);
check("история сократилась", V("HISTORY").length === 1, "записей: " + V("HISTORY").length);
check("ячейка снова доступна",
  document.querySelectorAll("#board-grid .q-cell.used").length === 1);

// ── 10. Архив ───────────────────────────────────────────────────────────
console.log("\n10. Архив");
window.archiveCurrentGame();
check("запись в архиве", V("getArchives()").length === 1);
check("номер раунда сохранён", V("getArchives()")[0].round === 0);
window.openArchive();
check("архив открыт", $("archive-overlay").classList.contains("open"));
check("в архиве 1 запись", document.querySelectorAll("#archive-list .archive-item").length === 1);

// deleteArchive открывает модалку — проверяем её
window.deleteArchive(0);
check("модалка пароля открылась", $("pwd-overlay").classList.contains("open"));
// неверный пароль
$("pwd-modal-input").value = "0000";
window.submitPwdModal();
check("неверный пароль не удаляет", V("getArchives()").length === 1);
check("показана ошибка", $("pwd-modal-error").textContent.includes("Неверный"));
check("модалка осталась открытой", $("pwd-overlay").classList.contains("open"));
// верный пароль
$("pwd-modal-input").value = "3321";
window.submitPwdModal();
check("запись удалена", V("getArchives()").length === 0);
check("модалка закрылась", !$("pwd-overlay").classList.contains("open"));
window.closeArchive();

// ── 11. Финальный экран и CSV ──────────────────────────────────────────
console.log("\n11. Финальный экран");
window.showFinal();
check("финальный экран открыт", $("final-screen").classList.contains("open"));
check("подиум построен", document.querySelectorAll("#final-podium .podium-place").length === 3);
check("таблица результатов", document.querySelectorAll("#final-table .final-row").length === 5);
window.exportCSV();
check("CSV сформирован без ошибок", true);
window.closeFinal();

// ── 12. Новая викторина ────────────────────────────────────────────────
console.log("\n12. Новая викторина");
window.startNewGame();
check("экран настройки команд", active() === "screen-setup");
check("счёт обнулён", V("SCORES").every(s => s === 0));
check("названия сброшены на стандартные", V("TEAM_NAMES")[0] === "Команда 1");
check("история пуста", V("HISTORY").length === 0);

// ── 13. Сохранение и восстановление ────────────────────────────────────
console.log("\n13. Сохранение состояния");
window.finishSetup();
window.selectRound(1);
window.selectBoardTeam(2);
window.selectQuestion(2, 2);
window.answerQuestion(true);
const saved = window.localStorage.getItem("quiz_active");
check("состояние записано в localStorage", !!saved);
window.startNewGame();                 // сбрасываем
check("состояние очищено при новой игре",
  !window.localStorage.getItem("quiz_active") ||
  JSON.parse(window.localStorage.getItem("quiz_active")).history.length === 0);

// ── 14. Клавиатура и доступность ───────────────────────────────────────
console.log("\n14. Доступность");
check("у ячеек есть tabindex", document.querySelectorAll('#board-grid [tabindex="0"]').length > 0);
check("тост — aria-live", $("toast").getAttribute("aria-live") === "polite");
check("финальный экран — role=dialog", $("final-screen").getAttribute("role") === "dialog");
check("есть :focus-visible в CSS", html.includes(":focus-visible"));
check("нет user-scalable=no", !html.includes("user-scalable=no"));
check("есть prefers-reduced-motion", html.includes("prefers-reduced-motion"));

// ── 15. Адаптивная сетка ────────────────────────────────────────────────
console.log("\n15. Адаптивность");
check("медиазапрос для мобильных", html.includes("@media(max-width:760px)"));
check("сетка перестраивается в 5 колонок", html.includes("grid-template-columns:repeat(5,1fr)"));
check("min-width:0 на ячейках", html.includes(".q-cell{min-width:0"));

// ── 16. Зрительский режим ──────────────────────────────────────────────
console.log("\n16. Зрительский режим");
check("есть разметка зрительского экрана", !!$("audience-screen"));
check("в скрипте есть определение режима", html.includes("view=audience"));
check("есть функция отрисовки", html.includes("function renderAudience()"));
check("есть функция трансляции", html.includes("function broadcast()"));
check("трансляция вызывается после ответа",
  html.includes("broadcast();\n  updateUndoButton();"));
check("состояние пишется в quiz_live", html.includes("quiz_live"));

// ── 17. Единые токены ───────────────────────────────────────────────────
console.log("\n17. Единые токены с лендингом");
check("подключены Archivo и Big Shoulders", html.includes("Big+Shoulders+Display"));
check("Playfair на 400-700, не 900", !html.includes("Playfair+Display:wght@700;900"));
check("золото единое #d8b787", html.includes("--gold:#d8b787"));
check("фон единый #070b12", html.includes("--ink:#070b12"));
check("числа на Big Shoulders", html.includes("font-family:var(--num)"));
check("токены встроены в файл", html.includes("--r-pill:999px"));

// ── Итог ────────────────────────────────────────────────────────────────
console.log("\n=== Результат ===");
if (errors.length) {
  console.log(`Ошибок: ${errors.length}`);
  errors.forEach(e => console.log("  ✗ " + e));
  process.exit(1);
}
console.log("Все проверки пройдены ✓");
