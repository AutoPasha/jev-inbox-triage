"""Независимая сверка сохраненных квитанций без сети и оплаты."""
import hashlib
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path

root = Path(__file__).resolve().parent
raw = (root / "dataset.json").read_bytes()
rows = json.loads(raw)["items"]
assert len(rows) == 40
assert Counter(r["expected"] for r in rows) == {"sales": 10, "support": 10, "other": 10, "clarify": 10}
assert len({r["id"] for r in rows}) == 40
criteria = json.loads((root / "criteria.json").read_text())
payload = {"model": "typesafe/jev", "state": {r["id"]: r["text"] for r in rows}, "questions": {r["id"]: {"type": "choice", "instructions": f"К какому классу относится сообщение `{r['id']}`? Судите только по его тексту.", "criteria": criteria} for r in rows}}
body = json.dumps(payload, ensure_ascii=False).encode()
assert b'"expected"' not in body
assert len(body) <= 60000
cost = Decimal(0)
results = []
for i in (1, 2, 3):
    record = json.loads((root / f"run-{i}.json").read_text())
    assert record["http_status"] == 200
    assert record["request_sha256"] == hashlib.sha256(body).hexdigest()
    assert record["dataset_sha256"] == hashlib.sha256(raw).hexdigest()
    answers = record["response"]["answers"]
    assert set(answers) == {r["id"] for r in rows}
    correct = sum(answers[r["id"]]["choice"] == r["expected"] for r in rows)
    assert correct == 40
    price = Decimal(str(record["response"]["usage"]["cost_rub"]))
    assert price >= 0
    cost += price
    results.append({"run": i, "correct": correct, "seconds": record["seconds"], "cost_rub": str(price)})
assert cost == Decimal("0.83699895")
assert cost < Decimal(5) < Decimal(50)
summary = {"dataset_size": 40, "independent_examples": 40, "runs": results, "total_cost_rub": str(cost), "budget_rub": 50, "gold_in_request": False}
(root / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(summary, ensure_ascii=False))
