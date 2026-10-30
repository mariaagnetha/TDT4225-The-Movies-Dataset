from pprint import pprint

import pandas as pd
from DbConnector import DbConnector
from data_cleaning import (
    clean_movies_metadata,
    clean_credits,
    clean_keywords,
    clean_ratings,
    convert_df_to_documents,
    DATA_DIR,
)

USE_SMALL_RATINGS = False
BATCH_SIZE = 50_000


class InsertProgram:

    def __init__(self):
        self.connection = DbConnector()
        self.client = self.connection.client
        self.db = self.connection.db

    def create_coll(self, collection_name):
        collection = self.db.create_collection(collection_name)
        print("Created collection: ", collection)

    def fetch_documents(self, collection_name):
        collection = self.db[collection_name]
        documents = collection.find({})
        for doc in documents:
            pprint(doc)

    def drop_coll(self, collection_name):
        collection = self.db[collection_name]
        collection.drop()

    def show_coll(self):
        collections = self.db.list_collection_names()
        print(collections)

    def build_movies(self):
        movies = pd.read_csv(DATA_DIR / "movies_metadata.csv", low_memory=False)
        movies = clean_movies_metadata(movies)

        credits = pd.read_csv(DATA_DIR / "credits.csv")
        credits = clean_credits(credits)

        keywords = pd.read_csv(DATA_DIR / "keywords.csv")
        keywords = clean_keywords(keywords)

        movies = movies.merge(credits, on="id", how="left")
        movies = movies.merge(keywords, on="id", how="left")
        for col in ["cast", "crew", "keywords"]:
            movies[col] = movies[col].apply(lambda x: x if isinstance(x, list) else [])
        movies["primary_genre"] = movies["genres"].apply(
            lambda x: x[0]["name"] if len(x) > 0 else None
        )
        movies["year"] = movies["release_date"].dt.year.astype("Int64")
        movies["decade"] = (movies["year"] // 10 * 10).astype("Int64")
        movies = movies.rename(columns={"id": "_id"})
        return movies

    def insert_movies(self, movies):
        collection = self.db["movies"]
        documents = convert_df_to_documents(movies)
        collection.insert_many(documents)
        print(f"Inserted {len(documents)} documents into collection 'movies'")

    def insert_ratings(self, movie_ids):
        ratings_file = "ratings_small.csv" if USE_SMALL_RATINGS else "ratings.csv"
        print("Reading", ratings_file)
        ratings = pd.read_csv(
            DATA_DIR / ratings_file,
            dtype={"userId": "int32", "movieId": "int32", "rating": "float32"},
        )
        links = pd.read_csv(DATA_DIR / "links.csv", usecols=["movieId", "tmdbId"])
        ratings = clean_ratings(ratings, links, movie_ids)
        ratings = ratings.rename(columns={"tmdbId": "movie_id", "userId": "user_id"})
        ratings = ratings[["user_id", "movie_id", "rating", "timestamp"]]
        collection = self.db["ratings"]
        for batch_start in range(0, len(ratings), BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, len(ratings))
            batch = ratings.iloc[batch_start:batch_end]
            documents = convert_df_to_documents(batch)
            collection.insert_many(documents)
            if batch_end % 1_000_000 == 0 or batch_end == len(ratings):
                print(
                    f"Inserted {batch_end} of {len(ratings)} ratings into collection 'ratings'"
                )

    def create_indexes(self):
        self.db["movies"].create_index([("overview", "text"), ("tagline", "text")])
        self.db["ratings"].create_index("user_id")
        self.db["ratings"].create_index("movie_id")
        print("Created indexes for collections 'movies' and 'ratings'")


def main():
    program = None
    try:
        program = InsertProgram()
        program.drop_coll(collection_name="movies")
        program.drop_coll(collection_name="ratings")
        program.create_coll(collection_name="movies")
        program.create_coll(collection_name="ratings")
        movies = program.build_movies()
        program.insert_movies(movies)
        movie_ids = movies["_id"].copy()
        del movies  # free memory
        program.insert_ratings(movie_ids)
        program.create_indexes()
        program.show_coll()
    except Exception as e:
        print("ERROR: Failed to use database:", e)
    finally:
        if program:
            program.connection.close_connection()


if __name__ == "__main__":
    main()
