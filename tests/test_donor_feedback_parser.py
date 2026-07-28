"""Parser tests for the Jotform donor feedback survey.

Adapted from nwmmb-db/tests/test_donor_feedback.py — only the parser-side
tests live here; ingestion handler tests stay in the nwmmb-db repo.
"""
from pathlib import Path

import pandas as pd
import pytest

from milk_data_drinker.jotform.feedback_survey import read_file

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "donor_feedback_example.csv"

CANONICAL_COLUMNS = [
    "submission_date", "approval_process_duration", "approval_delay_feedback",
    "prescreening_informative", "prescreening_feedback", "treated_with_respect",
    "respect_feedback", "donation_channel", "milk_drop_choice_reasons",
    "friendliness_of_staff", "gratitude_for_donation", "ease_of_arrangements",
    "shipping_container_experience", "shipping_instructions_clear",
    "shipping_feedback", "arrival_notification_received", "referral_likelihood",
    "other_feedback", "milk_drop",
]


@pytest.fixture
def df():
    assert FIXTURE.exists(), f"missing test fixture: {FIXTURE}"
    return read_file(str(FIXTURE))


def test_parser_emits_canonical_columns(df):
    assert set(df.columns) == set(CANONICAL_COLUMNS), (
        f"  unexpected: {sorted(set(df.columns) - set(CANONICAL_COLUMNS))}\n"
        f"  missing:    {sorted(set(CANONICAL_COLUMNS) - set(df.columns))}"
    )


def test_parser_drops_contact_column(df):
    """The free-text 'provide your name and/or donor number' column is dropped at parse
    time (user decision 2026-07-09): free-text donor self-identification isn't useful."""
    assert not [c for c in df.columns if "contact_you" in c]


def test_parser_multiselects_are_scalar_strings(df):
    """Jotform multi-selects arrive as newline-joined cell text; the parser must re-join
    with '; ' and never emit Python lists (pyodbc cannot bind a list parameter)."""
    for col in ("milk_drop_choice_reasons", "shipping_container_experience"):
        values = df[col].dropna()
        assert not values.map(lambda v: isinstance(v, list)).any(), f"{col} contains lists"
        assert not values.str.contains("\n").any(), f"{col} still newline-joined"
    assert df["milk_drop_choice_reasons"].dropna().str.contains("; ").any()


def test_parser_submission_date_is_datetime(df):
    assert pd.api.types.is_datetime64_any_dtype(df["submission_date"])
