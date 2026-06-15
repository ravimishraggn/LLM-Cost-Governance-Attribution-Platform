"""Phase 2 tests — the config-driven cost engine."""

from __future__ import annotations

import textwrap

import pytest

from llm_gateway.pricing import PricingBook
from llm_gateway.schemas import Provider

RAW = {
    "version": "test",
    "currency": "USD",
    "providers": {
        "openai": {
            "gpt-4o-mini": {"input": 0.15, "output": 0.60},
            "gpt-4o": {"input": 2.50, "output": 10.00},
        },
        "bedrock": {
            "anthropic.claude-haiku-4-5-v1:0": {"input": 1.00, "output": 5.00},
        },
    },
}


def test_cost_is_input_plus_output_per_million():
    book = PricingBook(RAW)
    # 1M input @ $0.15 + 1M output @ $0.60 = $0.75
    cost = book.cost(Provider.OPENAI, "gpt-4o-mini", 1_000_000, 1_000_000)
    assert cost == pytest.approx(0.75)


def test_input_and_output_priced_separately():
    book = PricingBook(RAW)
    cost = book.cost(Provider.OPENAI, "gpt-4o", 200_000, 50_000)
    expected = 200_000 / 1e6 * 2.50 + 50_000 / 1e6 * 10.00  # 0.50 + 0.50
    assert cost == pytest.approx(expected)


def test_dated_snapshot_id_resolves_via_prefix():
    book = PricingBook(RAW)
    # Provider returns a dated snapshot; it must still match the base entry.
    price = book.price_for(Provider.OPENAI, "gpt-4o-mini-2024-07-18")
    assert price is not None
    assert price.input_per_1m == 0.15


def test_unknown_model_records_zero_not_an_error():
    book = PricingBook(RAW)
    assert book.cost(Provider.OPENAI, "some-future-model", 1000, 1000) == 0.0


def test_same_model_priced_per_provider():
    book = PricingBook(RAW)
    # bedrock keys differ from openai keys — keying by (provider, model) matters.
    assert book.price_for(Provider.BEDROCK, "anthropic.claude-haiku-4-5-v1:0") is not None
    assert book.price_for(Provider.OPENAI, "anthropic.claude-haiku-4-5-v1:0") is None


def test_loads_from_yaml(tmp_path):
    import yaml

    p = tmp_path / "pricing.yaml"
    p.write_text(
        textwrap.dedent(
            """
            version: "yaml-test"
            currency: USD
            providers:
              openai:
                gpt-4o-mini:
                  input: 0.15
                  output: 0.60
            """
        ),
        encoding="utf-8",
    )
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    book = PricingBook(raw)
    assert book.version == "yaml-test"
    assert book.model_count == 1
