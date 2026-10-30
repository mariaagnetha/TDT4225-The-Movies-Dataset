import ast
import json
from pathlib import Path

import pandas as pd

DATA_DIR = Path("movies_datasets")
RATINGS_FILE = DATA_DIR / "ratings.csv"
RATINGS_SMALL_FILE = DATA_DIR / "ratings_small.csv"
# Use the smaller file while developing; switch to False for the full ratings dataset.
USE_SMALL_RATINGS_FOR_DEVELOPMENT = False


def clean_shifted_rows(movies_metadata):
    movies_metadata = movies_metadata.copy()
    movies_metadata["id"] = pd.to_numeric(movies_metadata["id"], errors="coerce")
    movies_metadata = movies_metadata.dropna(subset=["id"])
    movies_metadata["id"] = movies_metadata["id"].astype(int)
    print("Rows after removal of shifted rows:", movies_metadata.shape[0])
    return movies_metadata


def clean_duplicate_ids(movies_metadata):
    movies_metadata = movies_metadata.copy()
    movies_metadata["vote_count"] = pd.to_numeric(
        movies_metadata["vote_count"], errors="coerce"
    )
    movies_metadata = movies_metadata.sort_values("vote_count", ascending=False)
    movies_metadata = movies_metadata.drop_duplicates(subset=["id"], keep="first")
    print("Rows after removal of duplicate ids:", movies_metadata.shape[0])
    return movies_metadata


def clean_numeric_columns(movies_metadata):
    movies_metadata = movies_metadata.copy()
    numeric_columns = [
        "budget",
        "popularity",
        "revenue",
        "runtime",
        "vote_average",
        "vote_count",
    ]
    for col in numeric_columns:
        movies_metadata[col] = pd.to_numeric(movies_metadata[col], errors="coerce")

    for col in ["budget", "revenue"]:
        val_less_than_1000 = movies_metadata[col] < 1000
        print(f"{col}: {(val_less_than_1000).sum()} values replaced with None")
        movies_metadata.loc[val_less_than_1000, col] = None

    runtime_at_0 = movies_metadata["runtime"] == 0
    print(f"runtime: {runtime_at_0.sum()} values replaced with None")
    movies_metadata.loc[runtime_at_0, "runtime"] = None

    zero_vote_count = movies_metadata["vote_count"] == 0
    print(f"vote_average: {zero_vote_count.sum()} values replaced with None")
    movies_metadata.loc[zero_vote_count, "vote_average"] = None
    for col in ["budget", "revenue", "runtime", "vote_count"]:
        movies_metadata[col] = movies_metadata[col].astype("Int64")
    return movies_metadata


def clean_release_date(movies_metadata):
    movies_metadata = movies_metadata.copy()
    before_conversion = movies_metadata["release_date"].notna()
    movies_metadata["release_date"] = pd.to_datetime(
        movies_metadata["release_date"], errors="coerce", format="%Y-%m-%d"
    )
    dates_lost = before_conversion & movies_metadata["release_date"].isna()
    print(f"release_date: {dates_lost.sum()} values not able to convert")
    return movies_metadata


def clean_boolean_columns(movies_metadata):
    movies_metadata = movies_metadata.copy()
    for col in ["adult", "video"]:
        before_conversion = movies_metadata[col].notna()
        movies_metadata[col] = movies_metadata[col].map(
            {"True": True, "False": False, True: True, False: False}
        )
        boolean_lost = before_conversion & movies_metadata[col].isna()
        print(f"{col}: {boolean_lost.sum()} values not able to convert")
    return movies_metadata


def clean_empty_strings(movies_metadata):
    movies_metadata = movies_metadata.copy()
    for col in ["original_title", "overview", "tagline", "title", "homepage"]:
        empty_strings = movies_metadata[col].astype(str).str.strip() == ""
        print(f"{col}: {empty_strings.sum()} values replaced with None")
        movies_metadata.loc[empty_strings, col] = None
    return movies_metadata


def parse_nested_field(val):
    if pd.isna(val):
        return None
    if not isinstance(val, str):
        return val
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        try:
            return ast.literal_eval(val)
        except (ValueError, SyntaxError):
            return None


def clean_nested_fields(movies_metadata):
    movies_metadata = movies_metadata.copy()
    nested_fields = [
        "genres",
        "production_companies",
        "production_countries",
        "spoken_languages",
        "belongs_to_collection",
    ]
    for col in nested_fields:
        before_parsing = movies_metadata[col].notna()
        movies_metadata[col] = movies_metadata[col].apply(parse_nested_field)
        failed_parsing = before_parsing & movies_metadata[col].isna()
        print(f"{col}: {failed_parsing.sum()} values could not be parsed")

    for col in [
        "genres",
        "production_companies",
        "production_countries",
        "spoken_languages",
    ]:
        movies_metadata[col] = movies_metadata[col].apply(
            lambda x: [] if x is None else x
        )

    # Derived features used in the EDA; keep the original genre order.
    movies_metadata["release_year"] = movies_metadata["release_date"].map(
        lambda value: value.year if pd.notna(value) else None
    )
    movies_metadata["release_decade"] = movies_metadata["release_year"].map(
        lambda year: (year // 10) * 10 if pd.notna(year) else None
    )
    movies_metadata["primary_genre"] = movies_metadata["genres"].map(
        lambda genres: (
            genres[0].get("name")
            if isinstance(genres, list)
            and genres
            and isinstance(genres[0], dict)
            and isinstance(genres[0].get("name"), str)
            else None
        )
    )
    return movies_metadata


def clean_movies_metadata(movies_metadata):
    print("Original movies_metadata rows:", movies_metadata.shape[0])
    movies_metadata = clean_shifted_rows(movies_metadata)
    movies_metadata = clean_duplicate_ids(movies_metadata)
    movies_metadata = clean_numeric_columns(movies_metadata)
    movies_metadata = clean_release_date(movies_metadata)
    movies_metadata = clean_boolean_columns(movies_metadata)
    movies_metadata = clean_empty_strings(movies_metadata)
    movies_metadata = clean_nested_fields(movies_metadata)
    print("Rows after cleaning (movies_metadata):", movies_metadata.shape[0])
    return movies_metadata


def clean_credits(credits):
    credits = credits.copy()
    print("Original credits rows:", credits.shape[0])
    for col in ["cast", "crew"]:
        before_parsing = credits[col].notna()
        credits[col] = credits[col].apply(parse_nested_field)
        failed_parsing = before_parsing & credits[col].isna()
        print(f"{col}: {failed_parsing.sum()} values could not be parsed")
        credits[col] = credits[col].apply(lambda x: [] if x is None else x)

    def normalize_cast_order(cast):
        if not isinstance(cast, list):
            return cast
        normalized_cast = []
        for member in cast:
            if not isinstance(member, dict):
                normalized_cast.append(member)
                continue
            member = member.copy()
            if "order" in member:
                try:
                    order = float(member["order"])
                    member["order"] = int(order) if order.is_integer() else None
                except (TypeError, ValueError, OverflowError):
                    member["order"] = None
            normalized_cast.append(member)
        return normalized_cast

    credits["cast"] = credits["cast"].apply(normalize_cast_order)
    credits = credits.sort_values("crew", key=lambda x: x.apply(len), ascending=False)
    credits = credits.drop_duplicates(subset=["id"], keep="first")
    print("Rows after removal of duplicate ids (credits):", credits.shape[0])
    return credits


def clean_keywords(keywords):
    keywords = keywords.copy()
    print("Original keywords rows:", keywords.shape[0])
    before_parsing = keywords["keywords"].notna()
    keywords["keywords"] = keywords["keywords"].apply(parse_nested_field)
    failed_parsing = before_parsing & keywords["keywords"].isna()
    print(f"keywords: {failed_parsing.sum()} values could not be parsed")
    keywords["keywords"] = keywords["keywords"].apply(lambda x: [] if x is None else x)
    keywords = keywords.drop_duplicates(subset=["id"], keep="first")
    print("Rows after removal of duplicate ids (keywords):", keywords.shape[0])
    return keywords


def clean_ratings(ratings, links, movie_ids):
    print("Original ratings rows:", ratings.shape[0])

    # Normalize numeric identifiers and rating values before joining datasets.
    for col in ["userId", "movieId", "rating"]:
        ratings[col] = pd.to_numeric(ratings[col], errors="coerce")
    ratings = ratings.dropna(subset=["userId", "movieId"]).copy()
    ratings["userId"] = ratings["userId"].astype(int)
    ratings["movieId"] = ratings["movieId"].astype(int)

    # Normalize Unix timestamps to numbers, then interpret them consistently as UTC.
    timestamp_values = pd.to_numeric(ratings["timestamp"], errors="coerce")
    ratings["timestamp"] = pd.to_datetime(
        timestamp_values, unit="s", errors="coerce", utc=True
    )
    print(
        f"timestamp: {(ratings['timestamp'].isna()).sum()} values not able to convert"
    )
    ratings = ratings.merge(links[["movieId", "tmdbId"]], on="movieId", how="left")
    ratings = ratings.drop(columns=["movieId"])
    has_movie = ratings["tmdbId"].isin(movie_ids)
    print(
        f"ratings: {(~has_movie).sum()} rows could not be linked to a movie in movies_metadata"
    )
    ratings = ratings[has_movie].copy()
    ratings["tmdbId"] = ratings["tmdbId"].astype(int)
    ratings = ratings.sort_values("timestamp", ascending=False)
    duplicate_ratings = ratings.duplicated(subset=["userId", "tmdbId"], keep="first")
    print(
        f"ratings: {duplicate_ratings.sum()} duplicate user-movie pair ratings removed"
    )
    ratings = ratings[~duplicate_ratings]
    print("Rows after cleaning (ratings):", ratings.shape[0])
    return ratings


def convert_df_to_documents(df):
    """Replaces NaN, NaT and NA with None (needed for MongoDB) and converts a DataFrame to a list of dictionaries."""
    df = df.astype(object).where(pd.notnull(df), None)
    documents = df.to_dict(orient="records")
    return documents


if __name__ == "__main__":
    movies_metadata = pd.read_csv(DATA_DIR / "movies_metadata.csv", low_memory=False)
    movies_metadata = clean_movies_metadata(movies_metadata)
    credits = pd.read_csv(DATA_DIR / "credits.csv")
    credits = clean_credits(credits)
    keywords = pd.read_csv(DATA_DIR / "keywords.csv")
    keywords = clean_keywords(keywords)
    links = pd.read_csv(DATA_DIR / "links.csv")
    ratings_path = (
        RATINGS_SMALL_FILE if USE_SMALL_RATINGS_FOR_DEVELOPMENT else RATINGS_FILE
    )
    ratings = pd.read_csv(ratings_path, low_memory=False)
    ratings = clean_ratings(ratings, links, movies_metadata["id"])
