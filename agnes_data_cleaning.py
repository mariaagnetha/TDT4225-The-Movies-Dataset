from __future__ import annotations

import ast
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

DATA_DIR = Path("movies_datasets")
METADATA_FILE = DATA_DIR / "movies_metadata.csv"
CREDITS_FILE = DATA_DIR / "credits.csv"
KEYWORDS_FILE = DATA_DIR / "keywords.csv"
RATINGS_FILE = DATA_DIR / "ratings.csv"
RATINGS_SMALL_FILE = DATA_DIR / "ratings_small.csv"
LINKS_FILE = DATA_DIR / "links.csv"

# Keep True for development; use the full ratings.csv for the final import.
USE_SMALL_RATINGS_FOR_DEVELOPMENT = True

NESTED_FIELDS = {
    "movies_metadata": [
        "genres",
        "production_companies",
        "production_countries",
        "spoken_languages",
        "belongs_to_collection",
    ],
    "credits": ["cast", "crew"],
    "keywords": ["keywords"],
}

NUMERIC_METADATA_FIELDS = [
    "budget",
    "revenue",
    "runtime",
    "vote_average",
    "vote_count",
]


def parse_nested_value(value: Any) -> Any:
    # Parse JSON- or Python-literal-style data stored in a CSV cell.
    if not isinstance(value, str):
        return value

    stripped = value.strip()
    if not stripped:
        return value

    try:
        return json.loads(stripped)
    except (json.JSONDecodeError, TypeError):
        try:
            return ast.literal_eval(stripped)
        except (ValueError, SyntaxError):
            # Leave unexpected source values intact for the shared data-quality review.
            return value


def parse_nested_columns(dataframe: pd.DataFrame, fields: list[str]) -> pd.DataFrame:
    # Parse selected nested columns while preserving all rows.
    result = dataframe.copy()

    for field in fields:
        if field not in result.columns:
            continue

        parsed = result[field].map(parse_nested_value)

        if field == "belongs_to_collection":
            # This field is a single optional object rather than an array.
            parsed = parsed.map(
                lambda value: (
                    None if isinstance(value, str) and not value.strip() else value
                )
            )
        else:
            parsed = parsed.map(
                lambda value: (
                    [] if isinstance(value, str) and not value.strip() else value
                )
            )

        result[field] = parsed

    return result


def convert_numeric_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    # Convert valid metadata numbers and preserve invalid source values.
    result = dataframe.copy()

    for field in NUMERIC_METADATA_FIELDS:
        if field not in result.columns:
            continue

        def convert_if_valid(value: Any) -> Any:
            if pd.isna(value):
                return value

            try:
                number = pd.to_numeric(value, errors="raise")

                if (
                    field
                    in ("budget", "revenue", "runtime", "vote_count")  # noqa: B023
                    and math.isfinite(float(number))
                    and float(number).is_integer()
                ):
                    return int(number)

                return float(number)

            except (TypeError, ValueError, OverflowError):
                # Invalid values are retained for the shared data-quality decisions.
                return value

        result[field] = result[field].map(convert_if_valid)

    return result


def prepare_release_date_fields(dataframe: pd.DataFrame) -> pd.DataFrame:
    # Parse valid release dates and derive release year and decade.
    result = dataframe.copy()

    if "release_date" not in result.columns:
        return result

    def parse_date_if_valid(value: Any) -> Any:
        if pd.isna(value) or (isinstance(value, str) and not value.strip()):
            return value

        try:
            parsed = pd.to_datetime(value, errors="raise")
            return (
                parsed.to_pydatetime() if hasattr(parsed, "to_pydatetime") else parsed
            )
        except (TypeError, ValueError, OverflowError):
            # Invalid dates are left for the shared data-quality decisions.
            return value

    result["release_date"] = result["release_date"].map(parse_date_if_valid)

    def get_year(value: Any) -> int | None:
        if isinstance(value, (datetime, pd.Timestamp)):
            return value.year
        return None

    result["release_year"] = result["release_date"].map(get_year)
    result["release_decade"] = result["release_year"].map(
        lambda year: (year // 10) * 10 if year is not None else None
    )

    return result


def derive_primary_genre(dataframe: pd.DataFrame) -> pd.DataFrame:
    # Derive primary_genre from the first genre without changing genre order.
    result = dataframe.copy()

    if "genres" not in result.columns:
        return result

    def first_genre_name(genres: Any) -> str | None:
        if isinstance(genres, list) and genres and isinstance(genres[0], dict):
            name = genres[0].get("name")
            return name if isinstance(name, str) else None
        return None

    result["primary_genre"] = result["genres"].map(first_genre_name)
    return result


def prepare_ratings(dataframe: pd.DataFrame) -> pd.DataFrame:
    # Convert rating identifiers and values, and parse Unix timestamps as UTC.
    result = dataframe.copy()

    for field in ("userId", "movieId", "rating"):
        if field not in result.columns:
            continue

        def convert_if_valid(value: Any) -> Any:
            if pd.isna(value):
                return None

            try:
                number = pd.to_numeric(value, errors="raise")
                if field in ("userId", "movieId"):  # noqa: B023
                    if math.isfinite(float(number)) and float(number).is_integer():
                        return int(number)
                    return None
                return float(number)
            except (TypeError, ValueError, OverflowError):
                return None

        result[field] = result[field].map(convert_if_valid)

    if "timestamp" in result.columns:

        def convert_timestamp(value: Any) -> datetime | None:
            if pd.isna(value) or (isinstance(value, str) and not value.strip()):
                return None

            try:
                timestamp = float(value)
                if not math.isfinite(timestamp):
                    return None
                return datetime.fromtimestamp(timestamp, tz=UTC)
            except (TypeError, ValueError, OverflowError, OSError):
                return None

        result["timestamp"] = result["timestamp"].map(convert_timestamp)

    return result


def prepare_credits(dataframe: pd.DataFrame) -> pd.DataFrame:
    # Parse cast and crew, and normalize valid cast billing-order values.
    result = parse_nested_columns(dataframe, NESTED_FIELDS["credits"])

    if "cast" not in result.columns:
        return result

    def normalize_cast_order(cast: Any) -> Any:
        if not isinstance(cast, list):
            return cast

        normalized_cast = []
        for member in cast:
            if not isinstance(member, dict):
                normalized_cast.append(member)
                continue

            member_copy = member.copy()
            if "order" in member_copy:
                try:
                    order = float(member_copy["order"])
                    if math.isfinite(order) and order.is_integer():
                        member_copy["order"] = int(order)
                    else:
                        member_copy["order"] = None
                except (TypeError, ValueError, OverflowError):
                    member_copy["order"] = None

            normalized_cast.append(member_copy)

        return normalized_cast

    result["cast"] = result["cast"].map(normalize_cast_order)
    return result


def load_and_prepare_datasets() -> dict[str, pd.DataFrame]:
    """
    Load source CSVs and apply preparation steps.
    The returned dataframes are ready for the shared cleaning work to be added.
    """
    ratings_path = (
        RATINGS_SMALL_FILE if USE_SMALL_RATINGS_FOR_DEVELOPMENT else RATINGS_FILE
    )

    metadata = pd.read_csv(METADATA_FILE, low_memory=False)
    credits = pd.read_csv(CREDITS_FILE, low_memory=False)
    keywords = pd.read_csv(KEYWORDS_FILE, low_memory=False)
    links = pd.read_csv(LINKS_FILE, low_memory=False)
    ratings = pd.read_csv(ratings_path, low_memory=False)

    metadata = parse_nested_columns(metadata, NESTED_FIELDS["movies_metadata"])
    metadata = convert_numeric_columns(metadata)
    metadata = prepare_release_date_fields(metadata)
    metadata = derive_primary_genre(metadata)

    credits = prepare_credits(credits)
    keywords = parse_nested_columns(keywords, NESTED_FIELDS["keywords"])
    ratings = prepare_ratings(ratings)

    # Marias integration needed here: apply agreed section 1.2 data-quality
    # rules and section 1.5 cross-file ID/relationship rules to these dataframes.

    return {
        "metadata": metadata,
        "credits": credits,
        "keywords": keywords,
        "links": links,
        "ratings": ratings,
    }
