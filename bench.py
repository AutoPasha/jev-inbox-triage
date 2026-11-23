"""Повторяемый учебный замер Jev. Реальных писем и персональных данных нет."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import time
import urllib.request
from decimal import Decimal

ROOT = Path(__file__).resolve().parent
CRITERIA = {
    "sales": "Человек хочет заказать разработку, дизайн или автоматизацию и явно описал потребность. Вопрос о покупке или цене тоже сюда.",
    "support": "Человек сообщает об ошибке в уже используемом продукте или просит помочь с ним.",
    "other": "Предложение собственных услуг, реклама, обсуждение без запроса, благодарность или явный отказ от покупки.",
    "clarify": "По сообщению нельзя понять, хочет ли человек купить услугу или просит помочь с существующим продуктом. Нужен уточняющий вопрос.",
}
EXAMPLES = {
    "sales": [
        "Ищу разработчика, нужно связать каталог магазина с учетной системой.",
        "Сколько будет стоить лендинг для мастерской? Материалы готовы.",
        "Нужен дизайнер: переделать форму записи на сайте салона.",
        "Хотим автоматизировать перенос заявок из почты в таблицу. Возьметесь?",
        "Посоветуйте подрядчика для сайта гостиницы с бронированием.",
        "Есть бюджет на доработку интернет-магазина. Кому отправить задачу?",
        "Можно заказать у вас отчет по продажам с ежедневной отправкой?",
        "Ищу специалиста по ИИ для сортировки обращений в нашу компанию.",
        "Нашего сайта пока нет. Сделаете сайт для мебельного производства?",
        "Покажите ваши работы и условия: выбираем исполнителя для нового сайта.",
    ],
    "support": [
        "После обновления нашей установленной программы кнопка сохранения выдает ошибку.",
        "Не могу войти в уже оплаченный кабинет, восстановление пароля не приходит.",
        "Во вчерашнем отчете вашего сервиса исчезли строки. Помогите восстановить.",
        "У нас уже работает ваша интеграция, сегодня заказы перестали приходить.",
        "Как в купленной у вас программе выгрузить отчет в таблицу?",
        "На действующем сайте, который вы сделали, форма записи не отправляется.",
        "В вашем приложении все цены стали нулевыми после импорта. Что делать?",
        "Купленная подписка активна, но программа пишет, что доступ истек.",
        "Подключенный вчера бот дублирует каждое уведомление, исправьте, пожалуйста.",
        "В нашем существующем кабинете не открывается раздел заказов, вижу код 500.",
    ],
    "other": [
        "Я разработчик, делаю сайты и ищу заказы. Пишите в личку.",
        "Спасибо, больше ничего не нужно, все работает.",
        "Мы выбрали другого подрядчика. Предложение больше не актуально.",
        "Для своей мастерской сделал сайт сам, делюсь опытом без вопросов.",
        "Продаю курс по автоматизации отдела продаж, запись открыта.",
        "Обсуждали вчера, почему сайты гостиниц часто похожи друг на друга.",
        "Ничего заказывать не будем, просьба больше не писать.",
        "Если ищете разработчика, предлагаю свои услуги по созданию магазинов.",
        "Отчет получил, спасибо за помощь!",
        "Ищу работу дизайнером, могу показать портфолио.",
    ],
    "clarify": [
        "Можно с вами обсудить один вопрос?",
        "Сколько стоит?",
        "Мне нужна помощь.",
        "Здравствуйте, вы здесь?",
        "У нас вопрос по сайту.",
        "А с интеграциями работаете? Пока просто интересуюсь.",
        "У меня все сложно, можно подробнее рассказать?",
        "Есть небольшая задача, детали пришлю позже.",
        "К кому можно обратиться?",
        "Подскажите, как лучше поступить с нашей системой? Подробностей пока нет.",
    ],
}


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def prepare():
    if list(ROOT.glob("run-*.started")) or list(ROOT.glob("run-*.json")):
        raise SystemExit("Уже есть платные запуски; менять набор после замера запрещено.")
    rows = [{"text": text, "expected": label} for label, texts in EXAMPLES.items() for text in texts]
    random.Random(20261103).shuffle(rows)
    for i, row in enumerate(rows):
        row["id"] = f"m{i:02d}"
    dump(ROOT / "dataset.json", {"origin": "40 искусственных русскоязычных сообщений; авторская разметка до запроса; не реальные клиенты", "items": rows})
    dump(ROOT / "criteria.json", CRITERIA)
    print("Набор зафиксирован: 40 сообщений, четыре класса по десять, разметка не уйдет модели.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--run", type=int, choices=(1, 2, 3))
    args = parser.parse_args()
    if args.prepare:
        prepare()
        return
    if not args.run:
        parser.error("укажите --prepare или --run 1|2|3")
    # Потолок трех запросов сохраняется между запусками; повтор не перезапишет квитанцию.
    destination = ROOT / f"run-{args.run}.json"
    marker = ROOT / f"run-{args.run}.started"
    if destination.exists() or marker.exists():
        raise SystemExit("Этот запуск уже начат; повтор запрещен, проверьте сохраненную квитанцию.")
    rows = json.loads((ROOT / "dataset.json").read_text())["items"]
    criteria = json.loads((ROOT / "criteria.json").read_text())
    payload = {
        "model": "typesafe/jev",
        "state": {r["id"]: r["text"] for r in rows},
        "questions": {r["id"]: {"type": "choice", "instructions": f"К какому классу относится сообщение `{r['id']}`? Судите только по его тексту.", "criteria": criteria} for r in rows},
    }
    body = json.dumps(payload, ensure_ascii=False).encode()
    # Каталог Polza 03.11: 17,0184 ₽/млн входных токенов; берем запас до 20.
    # Байт как токен — консервативная оценка, а не измеренная токенизация.
    estimate = Decimal(len(body)) * Decimal("20") / Decimal(1000000)
    if len(body) > 60000 or estimate * 3 > Decimal("5"):
        raise SystemExit("Оценка трех запросов выше внутреннего потолка 5 ₽; сетевого вызова не будет.")
    token = os.environ.get("POLZA_KEY")
    if not token:
        raise SystemExit("Укажите API-ключ Polza.ai в переменной окружения POLZA_KEY.")
    request = urllib.request.Request("https://polza.ai/api/v1/systemone", data=body, headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    marker.write_text("Запрос начат; автоматических повторов нет.\n")
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=90) as response:
        raw = response.read()
        status = response.status
    output = json.loads(raw)
    dump(destination, {"http_status": status, "seconds": round(time.monotonic() - started, 3), "request_sha256": hashlib.sha256(body).hexdigest(), "request_bytes": len(body), "dataset_sha256": hashlib.sha256((ROOT / "dataset.json").read_bytes()).hexdigest(), "response": output})
    cost = output.get("usage", {}).get("cost_rub")
    if cost is None:
        raise SystemExit("В ответе нет цены. Квитанция сохранена, новые запросы не запускайте.")
    cost = Decimal(str(cost))
    costs = [Decimal(str(json.loads(p.read_text())["response"]["usage"]["cost_rub"])) for p in ROOT.glob("run-*.json")]
    if cost < 0 or sum(costs) > Decimal("5"):
        raise SystemExit("Сумма вне внутреннего потолка. Новые запросы не запускайте.")
    answers = output.get("answers", {})
    errors = [{"id": r["id"], "text": r["text"], "expected": r["expected"], "actual": answers.get(r["id"], {}).get("choice")} for r in rows if answers.get(r["id"], {}).get("choice") != r["expected"]]
    print(json.dumps({"run": args.run, "correct": len(rows) - len(errors), "total": len(rows), "cost_rub": str(cost), "total_cost_rub": str(sum(costs)), "seconds": round(time.monotonic() - started, 3), "errors": errors}, ensure_ascii=False))


if __name__ == "__main__":
    main()
