import logging
import os

import pandas as pd

from .._utils import clean_column_names

# Renamed by position: the source header for col 13 describes all three criteria at once,
# and cols 14/15 are blank in the Jotform export (pandas dedupes them to "No Label"/"No Label.1").
_RATING_RENAMES = {
    13: "friendliness_of_staff",
    14: "gratitude_for_donation",
    15: "ease_of_arrangements",
}

# Exactly one of these three is populated per row, selected by the channel question (col 7).
_MILK_DROP_COLS_IDX = (8, 9, 10)

# Jotform multi-select answers are joined with "\n" within a single cell; re-join with
# "; " so the value stays a scalar the DB can hold (pyodbc cannot bind a Python list).
_MULTISELECT_COLS_IDX = (12, 16)

# Applied after clean_column_names + lower(): the raw headers are full question
# sentences; alias them to short canonical names (see docs/report_column_dictionary.md).
_ALIASES = {
    "how_long_did_it_take_you_to_complete_the_milk_donor_approval_process":
        "approval_process_duration",
    "apologies_for_approval_taking_longer_than_expected_what_could_we_have_done_better":
        "approval_delay_feedback",
    "during_your_prescreening_interview_did_you_learn_everything_you_needed_to_know_about_becoming_a_milk_donor":
        "prescreening_informative",
    "it_sounds_like_we_could_have_done_a_better_job_how_can_we_improve":
        "prescreening_feedback",
    "during_your_communications_with_milk_bank_staff_do_you_feel_you_were_treated_with_respect":
        "treated_with_respect",
    "this_is_something_we_definitely_want_to_improve_please_share_any_feedback_you_feel_would_be_important_for_us_to_know":
        "respect_feedback",
    "what_option_did_you_choose_to_send_your_milk_donation_to_the_milk_bank":
        "donation_channel",
    "why_did_you_choose_this_location_check_all_that_apply":
        "milk_drop_choice_reasons",
    "please_check_all_that_apply_to_your_experience_ordering_and_receiving_shipping_containers":
        "shipping_container_experience",
    "the_instructions_for_shipping_my_milk_were_clear_and_easy_to_follow":
        "shipping_instructions_clear",
    "please_share_any_thoughts_you_have_about_improving_our_milk_drop_or_shipping_processes":
        "shipping_feedback",
    "did_you_receive_notification_when_your_milk_donation_arrived_at_nwmmb":
        "arrival_notification_received",
    "how_likely_are_you_to_refer_a_friend_family_member_or_co_worker_to_become_a_milk_donor":
        "referral_likelihood",
    "your_feedback_is_important_to_us_we_use_continuous_feedback_to_improve_the_milk_donation_experience_is_there_anything_else_you_would_like_us_to_know":
        "other_feedback",
}

# Free-text donor self-identification ("provide your name and/or donor number") —
# dropped as not useful downstream; staff handle contact requests in Jotform itself.
_DROP_COLS = [
    "if_you_would_like_a_staff_member_to_contact_you_regarding_any_of_your_feedback_please_provide_your_name_and_or_donor_number",
]


def read_file(file_path: str) -> pd.DataFrame:
    """Read a Jotform donor feedback survey export. Returns a DataFrame with one row per submission."""
    filename = os.path.basename(file_path)
    logging.info(f"Processing donor feedback survey: {filename}")

    df = pd.read_csv(file_path, encoding="utf-8-sig")
    columns = df.columns.tolist()

    df = df.rename(columns={columns[i]: name for i, name in _RATING_RENAMES.items()})

    milk_drop_cols = [columns[i] for i in _MILK_DROP_COLS_IDX]
    df["milk_drop"] = df[milk_drop_cols].bfill(axis=1).iloc[:, 0]
    df = df.drop(columns=milk_drop_cols)

    if "Submission Date" in df.columns:
        df["Submission Date"] = pd.to_datetime(df["Submission Date"], format="%d-%b-%y")

    for i in _MULTISELECT_COLS_IDX:
        col = columns[i]
        df[col] = df[col].apply(lambda v: "; ".join(v.split("\n")) if isinstance(v, str) else v)

    df = clean_column_names(df)
    df.columns = df.columns.str.lower()
    df = df.drop(columns=[c for c in _DROP_COLS if c in df.columns])
    df = df.rename(columns=_ALIASES)

    logging.info(f"Extracted {len(df)} rows from {filename}")
    return df
