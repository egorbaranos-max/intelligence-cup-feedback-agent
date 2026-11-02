"""Render saved model outputs as an offline HTML report; never call a model."""
import argparse
from datetime import datetime
from html import escape
import json
from pathlib import Path


KINDS = {"incident": "Сбой", "service_request": "Обслуживание", "feature_request": "Новая возможность",
         "usability": "Неудобство", "unknown": "Неясно"}


def e(value):
    return escape(str(value), quote=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((args.run / "manifest.json").read_text())
    inputs = {x["id"]: x for x in map(json.loads, args.inputs.read_text().splitlines())}
    results = list(map(json.loads, (args.run / "results.jsonl").read_text().splitlines()))
    calls = {x["call_id"]: x for x in map(json.loads, (args.run / "calls.jsonl").read_text().splitlines())}
    cards = json.loads((args.run / "cards.json").read_text())
    case_ids = [key for key, row in inputs.items() if row.get("origin") == "case_pdf"]
    synthetic_ids = [key for key, row in inputs.items() if row.get("origin") == "synthetic"]
    material = f"Материал: {len(case_ids)} текстов из задания и {len(synthetic_ids)} вымышленных проверочных примеров."
    navigation = '<a href="#cards">Карточки</a>'
    if case_ids:
        navigation += f'<a href="#{e(case_ids[0])}">Примеры из PDF</a>'
    if synthetic_ids:
        navigation += f'<a href="#{e(synthetic_ids[0])}">Проверочные ситуации</a>'
    navigation += '<a href="evaluation.md">Сравнение с предварительными ожиданиями</a>'
    sections = []
    for result in results:
        source = inputs[result["source_id"]]
        validation = result["extraction"]
        value = validation["value"] or {}
        status = "Проверить вручную" if value.get("status") == "needs_review" else "Формат принят"
        if not validation["ok"]:
            status = "Ответ отклонён"
        details = ""
        assignments = {a["intent_id"]: a for a in result.get("assignments", [])}
        for intent in value.get("intents", []):
            quotes = "".join(f'<blockquote>{e(ref["quote"])}</blockquote>' for ref in intent["evidence_refs"])
            details += f'<div class="intent"><b>{e(KINDS[intent["kind"]])}</b><p>{e(intent["statement"])}</p>{quotes}<small>Происхождение: {e(intent["origin"])}</small></div>'
            assignment = assignments.get(intent["intent_id"], {})
            verification = assignment.get("verification")
            if verification:
                verdict = (verification.get("value") or {}).get("verdict", "invalid")
                labels = {"supported": "Пожелание подтверждено повторной проверкой модели",
                          "unsupported": "Не подтверждено — в повторяемость не включено",
                          "unclear": "Неясно — в повторяемость не включено",
                          "invalid": "Ответ проверяющей модели отклонён"}
                reason = (verification.get("value") or {}).get("reason", "; ".join(verification.get("errors", [])))
                details += f'<p><b>{e(labels[verdict])}</b><br><small>{e(reason)}</small></p>'
            if assignment.get("status") == "needs_review":
                details += '<p class="error">Автоматическое включение в тему заблокировано; нужен разбор.</p>'
        if validation["errors"]:
            details += '<p class="error">' + e("; ".join(validation["errors"])) + '</p>'
        raw = calls[result["extraction_call"]]["raw_response"]
        origin = "Из условия, страница 6" if source["origin"] == "case_pdf" else "Вымышленный проверочный пример"
        sections.append(f'<article id="{e(source["id"])}"><div class="row"><b>{e(source["id"])}</b><span>{e(status)}</span></div><small>{origin}</small><h3>Обращение</h3><p>{e(source["text"])}</p><h3>Ответ модели</h3>{details}<details><summary>Исходный ответ без исправлений</summary><pre>{e(raw)}</pre></details></article>')
    card_blocks = []
    for card in cards:
        state = "Передана в локальную тестовую очередь" if card["recurring"] else "Порог повторяемости пока не достигнут"
        card_blocks.append(f'<article><b>{e(card["title"])}</b><p>{e(state)}</p><div class="numbers"><span><strong>{card["raw_sources"]}</strong>источников</span><span><strong>{card["independent_episodes"]}</strong>эпизодов</span><span><strong>{card["known_customers"]}</strong>известных клиентов</span></div><small>Объединение тем выполнила модель; корректность смысла нужно проверять отдельно.</small></article>')
    html = '''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Проверка агента на обращениях</title><style>
body{margin:0;background:#f3f5f7;color:#17232f;font:16px/1.55 system-ui,sans-serif}main{max-width:1000px;margin:auto;padding:44px 24px}h1{font-size:38px;line-height:1.12;max-width:780px}h2{margin-top:42px;font-size:27px}h3{font-size:15px;color:#527085;margin-bottom:4px}p{margin:10px 0}article,.notice{padding:22px 26px;background:white;border:1px solid #dbe3e9;border-radius:13px;margin:16px 0}small{color:#536b7d}blockquote{margin:14px 0;padding:8px 14px;border-left:3px solid #2f847d;background:#f2f8f7}.row{display:flex;gap:16px;justify-content:space-between}.row span{font-size:14px;color:#526b7c}.numbers{display:flex;gap:38px;margin:14px 0;flex-wrap:wrap}.numbers span{color:#536b7d;font-size:14px}.numbers strong{display:block;font-size:32px;color:#163d54}details{margin-top:20px}summary{cursor:pointer;color:#176b80}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;background:#f3f5f7;padding:14px;border-radius:6px}.intent+.intent{margin-top:22px;padding-top:18px;border-top:1px solid #dde6eb}.notice{background:#eaf2f6}.error{color:#973c32}a{color:#116a82}nav{display:flex;gap:18px;flex-wrap:wrap}.eyebrow{letter-spacing:.12em;text-transform:uppercase;font-size:12px;font-weight:700;color:#176b80}@media(max-width:600px){h1{font-size:30px}main{padding:25px 14px}article{padding:18px}.row{display:block}}</style><main>'''
    html += f'<div class="eyebrow">Intelligence Cup · локальный эксперимент</div><h1>Что агент увидел в обращениях</h1><p>Настоящие ответы Qwen3-4B, сохранённые без ручных исправлений.</p><div class="notice"><b>Граница опыта</b><p>Это текстовый запуск небольшой открытой Qwen на Mac. {e(material)} Корпоративная Qwen, звонки, изображения и денежный эффект здесь не испытаны. Проверка JSON и цитат не доказывает правильность смысла.</p></div>'
    html += f'<div class="numbers"><span><strong>{len(results)}</strong>обращений</span><span><strong>{manifest["valid_extractions"]}</strong>ответов прошли проверку формата и цитат</span><span><strong>{manifest["delivered_local_cards"]}</strong>карточек в тестовой очереди</span></div><p><small>Время обработки: {manifest["elapsed_seconds"]:.1f} с. Это один запуск; скорость рабочего потока не измерена. Дата окна для воспроизведения: {e(manifest["as_of"])}.</small></p><nav>{navigation}</nav>'
    html += '<h2 id="cards">Какие темы получились</h2>' + ("".join(card_blocks) or '<p>Тем для автоматического учета не создано.</p>')
    html += '<h2>Все обращения и ответы</h2>' + "".join(sections)
    html += f'<p><small>Модель: {e(manifest["model"]["model_id"])} · revision {e(manifest["model"]["revision"])}. Полные запросы и ответы: calls.jsonl. Код и контрольные суммы: manifest.json.</small></p></main></html>'
    (args.run / "report.html").write_text(html)
    print(args.run / "report.html")


if __name__ == "__main__":
    main()
