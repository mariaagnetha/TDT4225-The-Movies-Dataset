import ast
from pathlib import Path
import pandas as pd

DATA_DIR = Path("movies_datasets")


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
    movies_metadata["vote_count"] = movies_metadata["vote_count"].astype("Int64")

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
    ratings = ratings.copy()
    print("Original ratings rows:", ratings.shape[0])
    ratings["timestamp"] = pd.to_datetime(
        ratings["timestamp"], unit="s", errors="coerce"
    )
    print(
        f"timestamp: {(ratings['timestamp'].isna()).sum()} values not able to convert"
    )
    ratings = ratings.merge(links[["movieId", "tmdbId"]], on="movieId", how="left")
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
    ratings = pd.read_csv(DATA_DIR / "ratings.csv")
    ratings = clean_ratings(ratings, links, movies_metadata["id"])
