"""Exercise 3.4 (bonus) — compare RAGAS and DeepEval on the same 20 records.

Both frameworks score the saved answers in artifacts/actual_answers.json against
golden_dataset.json, using the same judge model (OPENAI_MODEL, default
gpt-4o-mini) and the same four RAG metrics:

    faithfulness, answer relevancy, context recall, context precision

Install the bonus dependencies first:

    pip install -r requirements-bonus.txt

Output: artifacts/framework_comparison.json plus a table in the terminal.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")
os.environ.setdefault("RAGAS_DO_NOT_TRACK", "true")

METRICS = ("faithfulness", "relevancy", "context_recall", "context_precision")
PASS_THRESHOLD = 0.5
MAX_ATTEMPTS = 3


def load_records(golden_path: Path, actual_path: Path) -> list[dict[str, Any]]:
    golden = {
        pair["id"]: pair
        for pair in json.loads(golden_path.read_text(encoding="utf-8"))["qa_pairs"]
    }
    answers = json.loads(actual_path.read_text(encoding="utf-8"))["answers"]
    records = []
    for answer in answers:
        pair = golden[answer["id"]]
        records.append(
            {
                "id": answer["id"],
                "difficulty": pair["difficulty"],
                "question": pair["question"],
                "answer": answer["actual_answer"],
                "reference": pair["expected_answer"],
                "contexts": [c["text"] for c in answer["retrieved_contexts"]],
            }
        )
    return records


def run_ragas(records: list[dict[str, Any]], model: str) -> dict[str, dict[str, float]]:
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    from ragas import EvaluationDataset, RunConfig, evaluate
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import (
        Faithfulness,
        LLMContextPrecisionWithReference,
        LLMContextRecall,
        ResponseRelevancy,
    )

    llm = LangchainLLMWrapper(ChatOpenAI(model=model, temperature=0))
    embeddings = LangchainEmbeddingsWrapper(
        OpenAIEmbeddings(model="text-embedding-3-small")
    )
    dataset = EvaluationDataset.from_list(
        [
            {
                "user_input": r["question"],
                "response": r["answer"],
                "reference": r["reference"],
                "retrieved_contexts": r["contexts"],
            }
            for r in records
        ]
    )
    result = evaluate(
        dataset,
        metrics=[
            Faithfulness(),
            ResponseRelevancy(),
            LLMContextRecall(),
            LLMContextPrecisionWithReference(),
        ],
        llm=llm,
        embeddings=embeddings,
        run_config=RunConfig(max_workers=4, timeout=180),
        show_progress=True,
    )
    frame = result.to_pandas()
    columns = {
        "faithfulness": "faithfulness",
        "relevancy": "answer_relevancy",
        "context_recall": "context_recall",
        "context_precision": "llm_context_precision_with_reference",
    }
    scores = {}
    for record, (_, row) in zip(records, frame.iterrows()):
        scores[record["id"]] = {
            name: _clean(row.get(column)) for name, column in columns.items()
        }
    return scores


def run_deepeval(
    records: list[dict[str, Any]], model: str
) -> dict[str, dict[str, float]]:
    from deepeval.metrics import (
        AnswerRelevancyMetric,
        ContextualPrecisionMetric,
        ContextualRecallMetric,
        FaithfulnessMetric,
    )
    from deepeval.test_case import LLMTestCase

    scores = {}
    for index, r in enumerate(records, start=1):
        test_case = LLMTestCase(
            input=r["question"],
            actual_output=r["answer"],
            expected_output=r["reference"],
            retrieval_context=r["contexts"],
        )
        metrics = {
            "faithfulness": FaithfulnessMetric(model=model, async_mode=False),
            "relevancy": AnswerRelevancyMetric(model=model, async_mode=False),
            "context_recall": ContextualRecallMetric(model=model, async_mode=False),
            "context_precision": ContextualPrecisionMetric(
                model=model, async_mode=False
            ),
        }
        row = {}
        for name, metric in metrics.items():
            row[name] = None
            for attempt in range(1, MAX_ATTEMPTS + 1):
                try:
                    metric.measure(test_case)
                    row[name] = _clean(metric.score)
                    break
                except Exception as exc:  # transient API errors: retry, then report
                    print(f"  DeepEval {r['id']} {name} attempt {attempt} failed: {exc}")
                    time.sleep(5 * attempt)
        scores[r["id"]] = row
        print(f"[DeepEval {index:02d}/{len(records)}] {r['id']} done")
    return scores


def _clean(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if number != number else round(number, 3)  # NaN -> None


def _avg(values: list[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return round(sum(present) / len(present), 3) if present else None


PASS_METRICS = ("faithfulness", "relevancy")


def _passed(row: dict[str, float | None]) -> bool:
    # Same answer-side rule for both frameworks: faithfulness and relevancy.
    return all(row[m] >= PASS_THRESHOLD for m in PASS_METRICS)


def summarize(
    records: list[dict[str, Any]], by_framework: dict[str, dict[str, dict]]
) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for framework, scores in by_framework.items():
        rows = [scores[r["id"]] for r in records]
        # A metric that errored is reported separately, never counted as a fail.
        errors = [
            r["id"]
            for r in records
            if any(scores[r["id"]].get(m) is None for m in PASS_METRICS)
        ]
        scored = [r for r in records if r["id"] not in errors]
        failures = [r["id"] for r in scored if not _passed(scores[r["id"]])]
        summary[framework] = {
            "averages": {m: _avg([row.get(m) for row in rows]) for m in METRICS},
            "pass_rate": (
                round(1 - len(failures) / len(scored), 3) if scored else None
            ),
            "failures": failures,
            "errors": errors,
        }
    names = list(by_framework)
    if len(names) == 2:
        a, b = (by_framework[n] for n in names)
        summary["agreement"] = {}
        for metric in METRICS:
            pairs = [
                (a[r["id"]].get(metric), b[r["id"]].get(metric))
                for r in records
                if a[r["id"]].get(metric) is not None
                and b[r["id"]].get(metric) is not None
            ]
            summary["agreement"][metric] = {
                "mean_abs_diff": _avg([abs(x - y) for x, y in pairs]),
                "spearman": _spearman(pairs),
            }
        fail_a, fail_b = (set(summary[n]["failures"]) for n in names)
        summary["failure_overlap"] = {
            "both": sorted(fail_a & fail_b),
            f"only_{names[0]}": sorted(fail_a - fail_b),
            f"only_{names[1]}": sorted(fail_b - fail_a),
        }
    return summary


def _rank(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def _spearman(pairs: list[tuple[float, float]]) -> float | None:
    if len(pairs) < 3:
        return None
    rx, ry = _rank([p[0] for p in pairs]), _rank([p[1] for p in pairs])
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    cov = sum((x - mx) * (y - my) for x, y in zip(rx, ry))
    vx = sum((x - mx) ** 2 for x in rx) ** 0.5
    vy = sum((y - my) ** 2 for y in ry) ** 0.5
    return round(cov / (vx * vy), 3) if vx and vy else None


def print_table(records, by_framework, summary) -> None:
    fmt = lambda v: "  -  " if v is None else f"{v:.3f}"  # noqa: E731
    names = list(by_framework)
    header = "| ID | " + " | ".join(
        f"{n[:2].upper()} {m[:6]}" for n in names for m in METRICS
    )
    print(header + " |")
    for r in records:
        cells = [fmt(by_framework[n][r["id"]].get(m)) for n in names for m in METRICS]
        print(f"| {r['id']} | " + " | ".join(cells) + " |")
    print(json.dumps(summary, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--golden", type=Path, default=ROOT / "golden_dataset.json")
    parser.add_argument(
        "--actual", type=Path, default=ROOT / "artifacts/actual_answers.json"
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "artifacts/framework_comparison.json"
    )
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY is not set (see .env.example).")
        return 1
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    records = load_records(args.golden, args.actual)

    by_framework: dict[str, dict[str, dict]] = {}
    timings: dict[str, float] = {}
    for name, runner in (("ragas", run_ragas), ("deepeval", run_deepeval)):
        print(f"Running {name} on {len(records)} records with {model}...")
        start = time.perf_counter()
        by_framework[name] = runner(records, model)
        timings[name] = round(time.perf_counter() - start, 1)

    summary = summarize(records, by_framework)
    summary["runtime_seconds"] = timings
    print_table(records, by_framework, summary)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            {
                "judge_model": model,
                "pass_rule": f"faithfulness and relevancy >= {PASS_THRESHOLD}",
                "summary": summary,
                "scores": by_framework,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"Saved: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
