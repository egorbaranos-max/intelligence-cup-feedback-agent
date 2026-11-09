// Сборка презентации из 10 слайдов на pptxgenjs.
// Контент слайдов — здесь; сценарий и источники цифр — presentation/outline.md;
// цифры — docs/assumptions.md. Запуск: node presentation/build_deck.js
// Выход: submission/presentation.pptx
const path = require("path");
const fs = require("fs");
const pptxgen = require("pptxgenjs");

const ROOT = path.resolve(__dirname, "..");
const THEME = JSON.parse(fs.readFileSync(path.join(__dirname, "theme.json"), "utf8"));
const C = THEME.colors;
const F = THEME.fonts;
const S = THEME.sizes;
const DIAG = (name) => path.join(ROOT, "docs", "diagrams", name);

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9"; // 10 x 5.625 in
pres.author = "Intelligence Cup team";
pres.title = "ИИ-агент для передачи пожеланий в продуктовые команды";
pres.theme = { headFontFace: F.head, bodyFontFace: F.body };

const wordCounts = {};
function countWords(slideNo, text) {
  const n = String(text).split(/\s+/).filter(Boolean).length;
  wordCounts[slideNo] = (wordCounts[slideNo] || 0) + n;
}

// ---------- Layouts ----------
pres.defineSlideMaster({
  title: "DARK",
  background: { color: C.navy },
  objects: [
    { text: { text: THEME.footer, options: { x: 0.5, y: 5.2, w: 7.5, h: 0.3, fontSize: 10, color: C.iceDark, fontFace: F.body, margin: 0 } } },
  ],
  slideNumber: { x: 9.1, y: 5.2, w: 0.5, h: 0.3, fontSize: 10, color: C.iceDark, fontFace: F.body },
});
pres.defineSlideMaster({
  title: "LIGHT",
  background: { color: C.white },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.35, w: 9.0, h: 0.9, fontSize: S.title, bold: true, color: C.navy, fontFace: F.head, align: "left", valign: "middle", margin: 0 }, text: "" } },
    { text: { text: THEME.footer, options: { x: 0.5, y: 5.2, w: 7.5, h: 0.3, fontSize: 10, color: C.muted, fontFace: F.body, margin: 0 } } },
  ],
  slideNumber: { x: 9.1, y: 5.2, w: 0.5, h: 0.3, fontSize: 10, color: C.muted, fontFace: F.body },
});

function slide(no, title) {
  const s = pres.addSlide({ masterName: "LIGHT" });
  s.addText(title, { placeholder: "title" });
  countWords(no, title);
  return s;
}
function text(s, no, str, opts) {
  s.addText(str, Object.assign({ isTextBox: true, fontFace: F.body, fontSize: S.body, color: C.ink, margin: 0, valign: "top" }, opts));
  countWords(no, str);
}
function card(s, no, x, y, w, h, big, small, fill, bigColor) {
  s.addShape(pres.ShapeType.roundRect, { x, y, w, h, fill: { color: fill }, line: { color: fill }, rectRadius: 0.08 });
  s.addText(big, { x: x + 0.15, y: y + 0.1, w: w - 0.3, h: h * 0.52, isTextBox: true, fontFace: F.head, fontSize: S.stat, bold: true, color: bigColor || C.navy, margin: 0, valign: "middle", align: "left", fit: "shrink" });
  s.addText(small, { x: x + 0.15, y: y + h * 0.6, w: w - 0.3, h: h * 0.36, isTextBox: true, fontFace: F.body, fontSize: S.caption + 1, color: C.ink, margin: 0, valign: "top" });
  countWords(no, big + " " + small);
}
function picture(s, file, x, y, maxW, maxH) {
  const sizeOf = require("child_process").execSync(`python3 -c "from PIL import Image;im=Image.open('${file}');print(im.size[0],im.size[1])"`).toString().trim().split(" ").map(Number);
  const ratio = sizeOf[0] / sizeOf[1];
  let w = maxW, h = maxW / ratio;
  if (h > maxH) { h = maxH; w = maxH * ratio; }
  s.addImage({ path: file, x: x + (maxW - w) / 2, y, w, h });
}
function tableOpts(extra) {
  return Object.assign({ fontFace: F.body, fontSize: 11, color: C.ink, border: { type: "solid", pt: 0.5, color: C.grid }, valign: "middle", margin: 0.05 }, extra || {});
}
function header(cells) {
  return cells.map((t) => ({ text: t, options: { bold: true, color: C.white, fill: { color: C.navy }, fontSize: 11 } }));
}

// ---------- 1. Титул (тёмный) ----------
{
  const s = pres.addSlide({ masterName: "DARK" });
  s.addText("7 дней", { x: 0.6, y: 0.9, w: 4.4, h: 1.6, isTextBox: true, fontFace: F.head, fontSize: 88, bold: true, color: C.amber, margin: 0, valign: "middle" });
  s.addText("Пожелания клиентов доходят до продукта за неделю, а не теряются в тикетах", { x: 0.6, y: 2.55, w: 8.6, h: 1.2, isTextBox: true, fontFace: F.head, fontSize: 28, bold: true, color: C.white, margin: 0, valign: "top" });
  s.addText("ИИ-агент для передачи пожеланий из техподдержки в продуктовые команды · решение кейса «Газпром нефти»", { x: 0.6, y: 3.95, w: 8.6, h: 0.7, isTextBox: true, fontFace: F.body, fontSize: 15, color: C.iceDark, margin: 0 });
  countWords(1, "7 дней Пожелания клиентов доходят до продукта за неделю, а не теряются в тикетах ИИ-агент для передачи пожеланий из техподдержки в продуктовые команды решение кейса Газпром нефти");
}

// ---------- 2. Проблема ----------
{
  const s = slide(2, "Сегодня пожелание проходит четыре руки и теряется на второй");
  const steps = [
    ["Обращение", "1 000 в день, звонки и заявки", C.ice, C.navy],
    ["Менеджер поддержки", "40 человек, решают инцидент", C.ice, C.navy],
    ["Выгрузка по запросу", "кто, как часто, сколько часов — неизвестно", C.amberLight, C.amber],
    ["Продуктовая команда", "видит инциденты, не видит пожелания", C.ice, C.navy],
  ];
  let x = 0.5;
  const w = 2.15, gap = 0.13, y = 1.45, h = 1.85;
  steps.forEach((st, i) => {
    s.addShape(pres.ShapeType.roundRect, { x, y, w, h, fill: { color: st[2] }, line: { color: st[2] }, rectRadius: 0.08 });
    s.addShape(pres.ShapeType.ellipse, { x: x + 0.15, y: y + 0.15, w: 0.4, h: 0.4, fill: { color: st[3] }, line: { color: st[3] } });
    s.addText(String(i + 1), { x: x + 0.15, y: y + 0.15, w: 0.4, h: 0.4, isTextBox: true, fontFace: F.head, fontSize: 14, bold: true, color: C.white, align: "center", valign: "middle", margin: 0 });
    text(s, 2, st[0], { x: x + 0.15, y: y + 0.62, w: w - 0.3, h: 0.62, fontSize: 14, bold: true, color: C.navy });
    text(s, 2, st[1], { x: x + 0.15, y: y + 1.27, w: w - 0.3, h: 0.55, fontSize: 11, color: C.ink });
    if (i < steps.length - 1) {
      s.addShape(pres.ShapeType.rightArrow, { x: x + w - 0.02, y: y + h / 2 - 0.12, w: gap + 0.04, h: 0.24, fill: { color: C.iceDark }, line: { color: C.iceDark } });
    }
    x += w + gap;
  });
  s.addShape(pres.ShapeType.ellipse, { x: 5.05, y: 3.5, w: 0.26, h: 0.26, fill: { color: C.amber }, line: { color: C.amber } });
  text(s, 2, "Здесь теряется пожелание: архив хранится год, но читается только по запросу", { x: 5.4, y: 3.45, w: 4.1, h: 0.6, fontSize: 13, color: C.ink });
  const chips = [["40", "менеджеров поддержки"], ["2", "канала: звонки и единое окно"], ["1 год", "хранится архив обращений"]];
  chips.forEach((c, i) => {
    const cx = 0.5 + i * 1.5;
    text(s, 2, c[0], { x: cx, y: 3.45, w: 1.4, h: 0.4, fontSize: 20, bold: true, color: C.navy, fontFace: F.head });
    text(s, 2, c[1], { x: cx, y: 3.85, w: 1.4, h: 0.5, fontSize: 10, color: C.muted });
  });
  text(s, 2, "Первое, что делаем, — измеряем: хронометраж анализа 2-4 недели до пилота", { x: 0.5, y: 4.55, w: 9, h: 0.45, fontSize: 13, italic: true, color: C.muted });
}

// ---------- 3. Семь примеров ----------
{
  const s = slide(3, "Из семи примеров условия ни один не является явным пожеланием");
  const typeCell = (t, fill, color) => ({ text: t, options: { fill: { color: fill }, color, bold: true, fontSize: 10.5, align: "center" } });
  const inc = (t) => typeCell(t, C.redLight, C.red);
  const srv = (t) => typeCell(t, C.ice, C.navy);
  const unk = (t) => typeCell(t, C.amberLight, "8A5A00");
  const rows = [
    header(["Обращение из условия", "Как размечает агент", "Почему"]),
    ["ИП вместо ООО в договоре оферты", unk("unknown"), "Сбой или ошибка данных: нужен контекст продукта"],
    ["Кнопка «Далее» не реагирует", inc("incident"), "Ожидаемая функция не работает"],
    ["Машина исчезла, повторно не добавить", inc("incident"), "Ожидаемая функция не работает"],
    ["Добавить телефон в заявку перед отгрузкой", srv("service_request"), "Разовая операция с записью"],
    ["Нет записи в электронную очередь, ошибка 404", inc("incident"), "Ожидаемая функция не работает"],
    ["Логин и пароль по уже заключённому договору", srv("service_request"), "Доступ, разовая помощь"],
    ["Не приходит SMS-код", inc("incident"), "Ожидаемая функция не работает"],
  ];
  s.addTable(rows, tableOpts({ x: 0.5, y: 1.4, w: 9.0, colW: [3.6, 1.6, 3.8], rowH: 0.34 }));
  text(s, 3, "Вывод: агент обязан различать тип, автора и цитату и считать повторы, иначе каждый сбой станет «пожеланием»", { x: 0.5, y: 4.45, w: 9, h: 0.55, fontSize: 13, bold: true, color: C.navy });
}

// ---------- 4. Как работает ----------
{
  const s = slide(4, "Модель читает, код решает");
  picture(s, DIAG("data-flow.png"), 0.5, 1.35, 5.6, 3.7);
  const items = [
    ["Qwen 3.8 извлекает", "намерения с цитатами из заявок, звонков (Qwen-ASR) и картинок (Qwen-VL)"],
    ["Код проверяет", "цитаты, права, идемпотентность; считает эпизоды и порог 3 за 30 дней"],
    ["PM решает", "карточка с цитатами в очереди владельца; в бэклог пишет человек"],
  ];
  let y = 1.45;
  items.forEach((it, i) => {
    s.addShape(pres.ShapeType.ellipse, { x: 6.4, y: y + 0.05, w: 0.42, h: 0.42, fill: { color: i === 1 ? C.amber : C.navy }, line: { color: i === 1 ? C.amber : C.navy } });
    s.addText(String(i + 1), { x: 6.4, y: y + 0.05, w: 0.42, h: 0.42, isTextBox: true, fontFace: F.head, fontSize: 14, bold: true, color: C.white, align: "center", valign: "middle", margin: 0 });
    text(s, 4, it[0], { x: 6.95, y, w: 2.6, h: 0.35, fontSize: 15, bold: true, color: C.navy });
    text(s, 4, it[1], { x: 6.95, y: y + 0.36, w: 2.6, h: 0.8, fontSize: 12, color: C.ink });
    y += 1.2;
  });
}

// ---------- 5. Архитектура и нагрузка ----------
{
  const s = slide(5, "Три приложения, пять сервисов, нагрузка посчитана");
  picture(s, DIAG("architecture.png"), 0.5, 1.35, 5.7, 3.6);
  card(s, 5, 6.5, 1.35, 3.0, 0.95, "1 000", "обращений в день: 40 менеджеров × 25", C.ice);
  card(s, 5, 6.5, 2.4, 3.0, 0.95, "1 200-2 000", "вызовов Qwen 3.8 в день", C.ice);
  card(s, 5, 6.5, 3.45, 3.0, 0.95, "25 ч", "аудио и 100 изображений в день", C.ice);
  text(s, 5, "Потоков: Qwen 2 · VL 1 · ASR 2 (RTF 0,10) — это потоки, не GPU", { x: 6.5, y: 4.5, w: 3.0, h: 0.5, fontSize: 11, color: C.muted });
}

// ---------- 6. Инструменты ----------
{
  const s = slide(6, "Восемь инструментов, ни одного права на запись в бэклог");
  const rows = [
    header(["Инструмент", "Что возвращает", "Ограничение прав"]),
    ["list_changes", "ID, версии, метаданные, next_cursor", "Только чтение источника"],
    ["get_evidence", "Обезличенные фрагменты и координаты", "ACL до выдачи"],
    ["transcribe · inspect_image", "Фрагменты речи и изображений", "Только внутренние ID, лимиты"],
    ["get_product_context", "Утверждённое поведение, словарь, владелец", "Справочник, не спрос"],
    ["find_topic_candidates", "До 25 доступных тем с evidence ID", "ACL до поиска"],
    ["save_analysis", "ID анализа или ошибка схемы и цитат", "topic_id создаёт код"],
    ["upsert_signal", "Счётчики и карточка по теме", "Получатель из справочника"],
    ["get_product_decision", "Статус, причина, связь с бэклогом", "approve и priority недоступны"],
  ];
  s.addTable(rows, tableOpts({ x: 0.5, y: 1.4, w: 9.0, colW: [2.6, 3.6, 2.8], rowH: 0.33 }));
  text(s, 6, "Плюс request_id, таймауты, DLQ, outbox и idempotency_key: повтор без дубля, SQL и внешние URL недоступны", { x: 0.5, y: 4.5, w: 9, h: 0.5, fontSize: 12, color: C.muted });
}

// ---------- 7. Промпт ----------
{
  const s = slide(7, "Промпт из шести блоков: убери любой — появится ложный спрос");
  const blocks = [
    ["Один JSON по схеме", "Текст вокруг JSON, скрытые рассуждения"],
    ["Авторство раньше типа", "Идея оператора становится спросом клиентов"],
    ["Пять типов намерений", "Семь сбоев из условия становятся «пожеланиями»"],
    ["Только span_id", "Переписанные цитаты, которые нельзя сверить"],
    ["Данные ≠ инструкции", "Тикет «добавь тему X» создаёт тему"],
    ["same только по объекту, действию, результату", "Разные просьбы склеиваются в одну тему"],
  ];
  const w = 2.9, h = 1.5, gx = 0.15, gy = 0.2;
  blocks.forEach((b, i) => {
    const col = i % 3, row = Math.floor(i / 3);
    const x = 0.5 + col * (w + gx), y = 1.45 + row * (h + gy);
    s.addShape(pres.ShapeType.roundRect, { x, y, w, h, fill: { color: C.ice }, line: { color: C.ice }, rectRadius: 0.08 });
    s.addShape(pres.ShapeType.ellipse, { x: x + 0.15, y: y + 0.15, w: 0.36, h: 0.36, fill: { color: C.navy }, line: { color: C.navy } });
    s.addText(String(i + 1), { x: x + 0.15, y: y + 0.15, w: 0.36, h: 0.36, isTextBox: true, fontFace: F.head, fontSize: 12, bold: true, color: C.white, align: "center", valign: "middle", margin: 0 });
    text(s, 7, b[0], { x: x + 0.6, y: y + 0.12, w: w - 0.75, h: 0.5, fontSize: 12.5, bold: true, color: C.navy });
    text(s, 7, "Без него: " + b[1], { x: x + 0.15, y: y + 0.72, w: w - 0.3, h: 0.7, fontSize: 11, color: C.ink });
  });
}

// ---------- 8. Прототип ----------
{
  const s = slide(8, "Прототип уже запущен: формат держится, смысл — ещё нет");
  card(s, 8, 0.5, 1.45, 2.15, 1.5, "48", "отложенных примеров, протокол зафиксирован до запуска", C.ice);
  card(s, 8, 2.8, 1.45, 2.15, 1.5, "47 из 48", "ответов по формату, Qwen3-4B", C.greenLight, C.green);
  card(s, 8, 5.1, 1.45, 2.15, 1.5, "3 из 4", "карточек смешивают темы, Qwen3-4B", C.redLight, C.red);
  card(s, 8, 7.4, 1.45, 2.1, 1.5, "2 из 3", "карточек верны, Qwen3-8B", C.amberLight, "8A5A00");
  s.addShape(pres.ShapeType.roundRect, { x: 0.5, y: 3.2, w: 9.0, h: 1.65, fill: { color: C.white }, line: { color: C.iceDark, pt: 1 }, rectRadius: 0.08 });
  text(s, 8, "Что исправляем до пилота", { x: 0.7, y: 3.3, w: 8.6, h: 0.35, fontSize: 14, bold: true, color: C.navy });
  text(s, 8, "Сопоставлению передаём полный текст обращения и справочник функций продукта. Порог релиза — точность и полнота на независимой разметке, а не демонстрация. Все ответы модели, включая ошибочные, сохранены в репозитории.", { x: 0.7, y: 3.7, w: 8.6, h: 1.1, fontSize: 12.5, color: C.ink });
}

// ---------- 9. Пилот и критерии ----------
{
  const s = slide(9, "Релиз только по числам: точность, полнота, покрытие за 7 дней");
  picture(s, DIAG("pilot-timeline.png"), 0.5, 1.35, 5.0, 3.7);
  card(s, 9, 5.9, 1.35, 3.6, 0.85, "≥ 90%", "точность извлечения, нижняя граница 95% интервала", C.ice);
  card(s, 9, 5.9, 2.3, 3.6, 0.85, "≥ 80%", "полнота извлечения по каждому каналу", C.ice);
  card(s, 9, 5.9, 3.25, 3.6, 0.85, "≥ 80%", "Coverage7: тем в очереди владельца за 7 дней", C.amberLight, "8A5A00");
  text(s, 9, "SLO: 95% обращений и 99% карточек за 24 ч. Стоп: обход ACL, рост часов поддержки", { x: 5.9, y: 4.25, w: 3.6, h: 0.7, fontSize: 11, color: C.muted });
}

// ---------- 10. Деньги (тёмный, закрывающий) ----------
{
  const s = pres.addSlide({ masterName: "DARK" });
  s.addText("2 760 часов в год и потолок вложений 2,99 млн ₽", { x: 0.5, y: 0.35, w: 9.0, h: 0.9, isTextBox: true, fontFace: F.head, fontSize: S.title, bold: true, color: C.white, margin: 0, valign: "middle" });
  countWords(10, "2 760 часов в год и потолок вложений 2,99 млн ₽");
  s.addChart(pres.ChartType.bar, [{ name: "PV доходов за 3 года, млн ₽", labels: ["Осторожный", "Базовый", "Благоприятный"], values: [0.283, 2.986, 10.994] }], {
    x: 0.5, y: 1.35, w: 5.0, h: 3.6, barDir: "col", chartColors: [C.amber], showValue: true, dataLabelPosition: "outEnd", dataLabelColor: C.white, dataLabelFontFace: "+mn-lt", dataLabelFontSize: 12, dataLabelFormatCode: "0.000",
    showTitle: true, title: "Предел дисконтированных вложений по сценариям, млн ₽", titleColor: C.white, titleFontFace: "+mn-lt", titleFontSize: 12,
    catAxisLabelColor: C.iceDark, catAxisLabelFontFace: "+mn-lt", catAxisLabelFontSize: 11, valAxisLabelColor: C.iceDark, valAxisLabelFontFace: "+mn-lt", valAxisLabelFontSize: 10,
    valGridLine: { color: "2F4A75", size: 0.5 }, catGridLine: { style: "none" }, showLegend: false, valAxisMaxVal: 12,
  });
  const dark = (x, y, w, h, big, small) => {
    s.addShape(pres.ShapeType.roundRect, { x, y, w, h, fill: { color: C.navyDeep }, line: { color: "2F4A75", pt: 1 }, rectRadius: 0.08 });
    s.addText(big, { x: x + 0.15, y: y + 0.08, w: w - 0.3, h: h * 0.5, isTextBox: true, fontFace: F.head, fontSize: 30, bold: true, color: C.amber, margin: 0, valign: "middle", fit: "shrink" });
    s.addText(small, { x: x + 0.15, y: y + h * 0.58, w: w - 0.3, h: h * 0.4, isTextBox: true, fontFace: F.body, fontSize: 11.5, color: C.iceDark, margin: 0 });
    countWords(10, big + " " + small);
  };
  dark(5.9, 1.35, 3.6, 1.1, "2 760 ч/год", "высвобождает поддержка с учётом новой работы PM и QA");
  dark(5.9, 2.6, 3.6, 1.1, "≤ 2,986 млн ₽", "окупаемость за 3 года при b = 1,656 млн ₽, r = 20%");
  s.addText("Ставка ЦБ 14% (23.10.2026). Альтернативы: текущий процесс, BI-отчёт, минимальный агент, депозит. Деньги — только подтверждённые реестром; до него эффект в часах.", { x: 5.9, y: 3.85, w: 3.6, h: 1.1, isTextBox: true, fontFace: F.body, fontSize: 11, color: C.iceDark, margin: 0 });
  countWords(10, "Ставка ЦБ 14% 23.10.2026 Альтернативы текущий процесс BI-отчёт минимальный агент депозит Деньги только подтверждённые реестром до него эффект в часах");
}

// ---------- Запись ----------
const out = path.join(ROOT, "submission", "presentation.pptx");
pres.writeFile({ fileName: out }).then(() => {
  const slides = Object.keys(wordCounts).length;
  console.log("presentation.pptx: слайдов " + slides);
  Object.entries(wordCounts).forEach(([k, v]) => console.log("  слайд " + k + ": слов вне таблиц " + v + (v > 60 ? "  <-- много" : "")));
});
