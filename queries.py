from pprint import pprint
from DbConnector import DbConnector


class QueryProgram:

    def __init__(self):
        self.connection = DbConnector()
        self.client = self.connection.client
        self.db = self.connection.db

    def query1(self):
        """Considering only crew with job = Director, which 10 directors with ≥ 5 movies
        have the highest median revenue?
        Also report each director’s movie count and mean vote_average."""
        results = self.db.movies.aggregate(
            [
                {"$unwind": "$crew"},
                {"$match": {"crew.job": "Director"}},
                {
                    "$group": {
                        "_id": "$crew.id",
                        "director": {"$first": "$crew.name"},
                        "movie_count": {"$sum": 1},
                        "median_revenue": {
                            "$median": {"input": "$revenue", "method": "approximate"}
                        },
                        "mean_vote_average": {"$avg": "$vote_average"},
                    }
                },
                {"$match": {"movie_count": {"$gte": 5}}},
                {"$sort": {"median_revenue": -1}},
                {"$limit": 10},
                {"$set": {"mean_vote_average": {"$round": ["$mean_vote_average", 2]}}},
            ]
        )
        for result in results:
            pprint(result)

    def query2(self):
        """List actor pairs have co-starred in ≥ 3 movies together, their number of
        co-appearances, and their average movie vote_average. Sort by number of
        co-appearances."""
        results = self.db.movies.aggregate(
            [
                {"$project": {"actor1": "$cast", "actor2": "$cast", "vote_average": 1}},
                {"$unwind": "$actor1"},
                {"$unwind": "$actor2"},
                {"$match": {"$expr": {"$lt": ["$actor1.id", "$actor2.id"]}}},
                {
                    "$group": {
                        "_id": {
                            "movie_id": "$_id",
                            "actor1_id": "$actor1.id",
                            "actor2_id": "$actor2.id",
                        },
                        "actor1": {"$first": "$actor1.name"},
                        "actor2": {"$first": "$actor2.name"},
                        "vote_average": {"$first": "$vote_average"},
                    }
                },
                {
                    "$group": {
                        "_id": {
                            "actor1_id": "$_id.actor1_id",
                            "actor2_id": "$_id.actor2_id",
                        },
                        "actor1": {"$first": "$actor1"},
                        "actor2": {"$first": "$actor2"},
                        "co_appearances": {"$sum": 1},
                        "avg_movie_vote": {"$avg": "$vote_average"},
                    }
                },
                {"$match": {"co_appearances": {"$gte": 3}}},
                {"$sort": {"co_appearances": -1}},
                {"$set": {"avg_movie_vote": {"$round": ["$avg_movie_vote", 2]}}},
            ]
        )
        results = list(results)
        print("Number of actor pairs with >= 3 movies together:", len(results))
        for result in results[:20]:
            pprint(result)

    def query3(self):
        """List the top 10 actors (with ≥ 10 credited movies) that have the widest genre
        breadth. Report the actor, the number of distinct genres they’ve appeared in,
        and up to 5 example genres."""
        results = self.db.movies.aggregate(
            [
                {"$unwind": "$cast"},
                {"$unwind": {"path": "$genres", "preserveNullAndEmptyArrays": True}},
                {
                    "$group": {
                        "_id": "$cast.id",
                        "actor": {"$first": "$cast.name"},
                        "distinct_genres": {"$addToSet": "$genres.name"},
                        "movies": {"$addToSet": "$_id"},
                    }
                },
                {
                    "$project": {
                        "actor": 1,
                        "distinct_genre_count": {"$size": "$distinct_genres"},
                        "movie_count": {"$size": "$movies"},
                        "example_genres": {"$slice": ["$distinct_genres", 5]},
                    }
                },
                {"$match": {"movie_count": {"$gte": 10}}},
                {"$sort": {"distinct_genre_count": -1, "movie_count": -1}},
                {"$limit": 10},
            ]
        )
        for result in results:
            pprint(result)

    def query4(self):
        """For film collections (belongs_to_collection.name not null) with ≥ 3 movies, which
        10 collections have the largest total revenue?
        For each, report movie count, total revenue, median vote_average, and the
        earliest → latest release date."""
        results = self.db.movies.aggregate(
            [
                {"$match": {"belongs_to_collection.name": {"$ne": None}}},
                {
                    "$group": {
                        "_id": "$belongs_to_collection.name",
                        "movie_count": {"$sum": 1},
                        "total_revenue": {"$sum": "$revenue"},
                        "median_vote_average": {
                            "$median": {
                                "input": "$vote_average",
                                "method": "approximate",
                            }
                        },
                        "earliest_release_date": {"$min": "$release_date"},
                        "latest_release_date": {"$max": "$release_date"},
                    }
                },
                {"$match": {"movie_count": {"$gte": 3}}},
                {"$sort": {"total_revenue": -1}},
                {"$limit": 10},
                {
                    "$set": {
                        "earliest_release_date": {
                            "$dateToString": {
                                "format": "%Y-%m-%d",
                                "date": "$earliest_release_date",
                            }
                        },
                        "latest_release_date": {
                            "$dateToString": {
                                "format": "%Y-%m-%d",
                                "date": "$latest_release_date",
                            }
                        },
                    }
                },
            ]
        )
        for result in results:
            pprint(result)

    def query5(self):
        """By decade (e.g., 1970s, 1980s, …) and primary genre (first element in genres),
        what is the median runtime and movie count?
        List results sorted by decade then median runtime (desc)."""
        results = self.db.movies.aggregate(
            [
                {
                    "$match": {
                        "decade": {"$ne": None},
                        "primary_genre": {"$ne": None},
                        "status": "Released",
                    }
                },
                {
                    "$group": {
                        "_id": {"decade": "$decade", "primary_genre": "$primary_genre"},
                        "median_runtime": {
                            "$median": {"input": "$runtime", "method": "approximate"}
                        },
                        "movie_count": {"$sum": 1},
                    }
                },
                {"$sort": {"_id.decade": 1, "median_runtime": -1}},
            ]
        )
        for result in results:
            pprint(result, width=120)

    def query6(self):
        """For each movie’s top-billed 5 cast (by order), what is the proportion of female
        cast?
        Aggregate by decade and list decades sorted by average female proportion
        (desc), including movie counts used. Unknown gender may be ignored."""
        results = self.db.movies.aggregate(
            [
                {"$match": {"decade": {"$ne": None}, "status": "Released"}},
                {
                    "$project": {
                        "decade": 1,
                        "top_5_cast": {
                            "$slice": [
                                {
                                    "$sortArray": {
                                        "input": "$cast",
                                        "sortBy": {"order": 1},
                                    }
                                },
                                5,
                            ]
                        },
                    }
                },
                {"$unwind": "$top_5_cast"},
                {"$match": {"top_5_cast.gender": {"$in": [1, 2]}}},
                {
                    "$group": {
                        "_id": {"decade": "$decade", "movie_id": "$_id"},
                        "female_count": {
                            "$sum": {
                                "$cond": [{"$eq": ["$top_5_cast.gender", 1]}, 1, 0]
                            }
                        },
                        "total_count": {"$sum": 1},
                    }
                },
                {
                    "$group": {
                        "_id": "$_id.decade",
                        "avg_female_proportion": {
                            "$avg": {"$divide": ["$female_count", "$total_count"]}
                        },
                        "movie_count": {"$sum": 1},
                    }
                },
                {"$sort": {"avg_female_proportion": -1}},
                {
                    "$set": {
                        "avg_female_proportion": {
                            "$round": ["$avg_female_proportion", 3]
                        }
                    }
                },
            ]
        )
        for result in results:
            pprint(result)

    def query7(self):
        """Using a text search over overview and tagline, which 20 movies matching “noir”
        or “neo-noir” (and vote_count ≥ 50) have the highest vote_average?
        Return title, year, vote_average, and vote_count."""
        results = self.db.movies.aggregate(
            [
                {
                    "$match": {
                        "$text": {"$search": "noir"},
                        "vote_count": {"$gte": 50},
                    }
                },
                {
                    "$project": {
                        "title": 1,
                        "year": 1,
                        "vote_average": 1,
                        "vote_count": 1,
                    }
                },
                {"$sort": {"vote_average": -1, "vote_count": -1}},
                {"$limit": 20},
            ]
        )
        for result in results:
            pprint(result)

    def query8(self):
        """Which 20 director–actor pairs with ≥ 3 collaborations (same movie) have the
        highest mean vote_average, considering only movies with vote_count ≥ 100?
        Include the pair’s films count and mean revenue."""
        results = self.db.movies.aggregate(
            [
                {"$match": {"vote_count": {"$gte": 100}}},
                {"$unwind": "$crew"},
                {"$match": {"crew.job": "Director"}},
                {"$unwind": "$cast"},
                {
                    "$group": {
                        "_id": {
                            "movie_id": "$_id",
                            "director_id": "$crew.id",
                            "actor_id": "$cast.id",
                        },
                        "director": {"$first": "$crew.name"},
                        "actor": {"$first": "$cast.name"},
                        "vote_average": {"$first": "$vote_average"},
                        "revenue": {"$first": "$revenue"},
                    }
                },
                {
                    "$group": {
                        "_id": {
                            "director_id": "$_id.director_id",
                            "actor_id": "$_id.actor_id",
                        },
                        "director": {"$first": "$director"},
                        "actor": {"$first": "$actor"},
                        "films_count": {"$sum": 1},
                        "mean_vote_average": {"$avg": "$vote_average"},
                        "mean_revenue": {"$avg": "$revenue"},
                    }
                },
                {"$match": {"films_count": {"$gte": 3}}},
                {"$sort": {"mean_vote_average": -1, "films_count": -1}},
                {"$limit": 20},
                {
                    "$set": {
                        "mean_vote_average": {"$round": ["$mean_vote_average", 2]},
                        "mean_revenue": {"$round": ["$mean_revenue", 2]},
                    }
                },
            ]
        )
        for result in results:
            pprint(result)

    def query9(self):
        """Among movies where original_language ≠ "en" but at least one production
        company or country is United States, which are the top 10 original languages by
        count?
        For each language, report the count and one example title."""
        results = self.db.movies.aggregate(
            [
                {
                    "$match": {
                        "original_language": {"$nin": ["en", None]},
                        "production_countries.iso_3166_1": "US",
                    }
                },
                {
                    "$group": {
                        "_id": "$original_language",
                        "count": {"$sum": 1},
                        "example_title": {"$first": "$title"},
                    }
                },
                {"$sort": {"count": -1}},
                {"$limit": 10},
            ]
        )
        for result in results:
            pprint(result)

    def query10(self):
        """For each user, what is their ratings count, population variance of ratings, and
        number of distinct genres rated?
        List the top 10 most genre-diverse users, and separately the top 10
        highest-variance users (only users with ≥ 20 ratings)."""
        genre_map_to_movie = {}
        for movie in self.db.movies.find({}, {"_id": 1, "genres.name": 1}):
            genre_map_to_movie[movie["_id"]] = set(
                genre["name"] for genre in movie.get("genres", []) if "name" in genre
            )
        results = self.db.ratings.aggregate(
            [
                {
                    "$group": {
                        "_id": "$user_id",
                        "ratings_count": {"$sum": 1},
                        "ratings_stdDev": {"$stdDevPop": "$rating"},
                        "movie_ids": {"$addToSet": "$movie_id"},
                    }
                },
                {"$match": {"ratings_count": {"$gte": 20}}},
            ]
        )
        users = []
        for user in results:
            distinct_genres = set()
            for movie_id in user["movie_ids"]:
                distinct_genres.update(genre_map_to_movie.get(movie_id, set()))
            users.append(
                {
                    "user_id": user["_id"],
                    "ratings_count": user["ratings_count"],
                    "ratings_variance": round(user["ratings_stdDev"] ** 2, 4),
                    "distinct_genre_count": len(distinct_genres),
                }
            )
        users.sort(key=lambda x: (-x["distinct_genre_count"], -x["ratings_count"]))
        print("Top 10 most genre-diverse users:")
        for user in users[:10]:
            pprint(user)

        users.sort(key=lambda x: (-x["ratings_variance"], -x["ratings_count"]))
        print("\nTop 10 highest-variance users:")
        for user in users[:10]:
            pprint(user)


def main():
    program = None
    try:
        program = QueryProgram()
        program.query1()
        program.query2()
        program.query3()
        program.query4()
        program.query5()
        program.query6()
        program.query7()
        program.query8()
        program.query9()
        program.query10()
    except Exception as e:
        print("ERROR: Failed to use database:", e)
    finally:
        if program:
            program.connection.close_connection()


if __name__ == "__main__":
    main()
