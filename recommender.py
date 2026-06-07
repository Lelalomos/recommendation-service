import pandas as pd
import numpy as np
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

class NetflixRecommender:
    def __init__(self, movies_path, tv_shows_path):
        self.movies_path = movies_path
        self.tv_shows_path = tv_shows_path
        self.df = None
        self.tfidf = None
        self.tfidf_matrix = None
        self.C = None  # Global mean rating for Bayesian average
        self.m = None  # Minimum vote count threshold for Bayesian average
        
    def load_and_preprocess(self):
        # 1. Load datasets
        movies = pd.read_csv(self.movies_path)
        tv_shows = pd.read_csv(self.tv_shows_path)
        
        # Align columns
        common_cols = [
            'show_id', 'type', 'title', 'director', 'cast', 'country', 
            'date_added', 'release_year', 'rating', 'genres', 'language', 
            'description', 'popularity', 'vote_count', 'vote_average'
        ]
        
        df_movies = movies[common_cols].copy()
        df_tv = tv_shows[common_cols].copy()
        
        # 2. Add custom duration info if available
        # Movie duration in this dataset is null, but TV show duration is season count.
        # We can extract duration for TV shows and leave movies as "N/A"
        df_movies['duration'] = "N/A"
        df_tv['duration'] = tv_shows['duration']
        
        # Combine
        self.df = pd.concat([df_movies, df_tv], ignore_index=True)
        
        # Fill missing values
        self.df['director'] = self.df['director'].fillna('')
        self.df['cast'] = self.df['cast'].fillna('')
        self.df['country'] = self.df['country'].fillna('')
        self.df['genres'] = self.df['genres'].fillna('')
        self.df['description'] = self.df['description'].fillna('')
        
        # Clean titles for exact/fuzzy searches
        self.df['clean_title'] = self.df['title'].apply(self._clean_title)
        
        # 3. Calculate Bayesian Weighted Rating
        # Formula: (v / (v + m)) * R + (m / (v + m)) * C
        self.C = self.df['vote_average'].mean()
        # Use 30th percentile of vote count as m
        self.m = self.df['vote_count'].quantile(0.3)
        if self.m < 1:
            self.m = 5.0 # default to 5 votes min
            
        self.df['weighted_rating'] = self.df.apply(
            lambda r: (r['vote_count'] / (r['vote_count'] + self.m)) * r['vote_average'] + 
                      (self.m / (r['vote_count'] + self.m)) * self.C, 
            axis=1
        )
        
        # Normalize popularity for hybrid scoring
        # Use log scale since popularity is highly skewed
        log_pop = np.log1p(self.df['popularity'])
        self.df['normalized_popularity'] = (log_pop - log_pop.min()) / (log_pop.max() - log_pop.min())
        
        # Normalize weighted rating between 0 and 1
        min_wr = self.df['weighted_rating'].min()
        max_wr = self.df['weighted_rating'].max()
        self.df['normalized_rating'] = (self.df['weighted_rating'] - min_wr) / (max_wr - min_wr)
        
        # 4. Build TF-IDF Soup
        self.df['soup'] = self.df.apply(self._create_soup, axis=1)
        
        # 5. Fit Vectorizer
        self.tfidf = TfidfVectorizer(stop_words='english', max_features=15000, ngram_range=(1, 2))
        self.tfidf_matrix = self.tfidf.fit_transform(self.df['soup'])
        
        print("Data loaded, preprocessed, and TF-IDF indexed successfully.")
        
    def _clean_title(self, title):
        if not isinstance(title, str):
            return ""
        return re.sub(r'[^a-zA-Z0-9\s]', '', title.lower()).strip()
        
    def _create_soup(self, row):
        # We clean and concatenate keywords to make TF-IDF matching more robust.
        genres = str(row['genres']).lower().replace(',', '')
        description = str(row['description']).lower()
        
        # Actors: remove spaces to treat "Bruce Willis" as a single token "brucewillis"
        cast = ' '.join([actor.strip().lower().replace(' ', '') for actor in str(row['cast']).split(',') if actor])
        
        # Directors: remove spaces
        director = ' '.join([d.strip().lower().replace(' ', '') for d in str(row['director']).split(',') if d])
        
        # Country
        country = str(row['country']).lower().replace(' ', '').replace(',', ' ')
        
        # Type
        item_type = str(row['type']).lower()
        
        # We repeat genres and director to give them higher weights than description
        soup = f"{genres} {genres} {genres} {director} {director} {cast} {country} {item_type} {description}"
        return soup

    def search_titles(self, query, top_n=5):
        """Search titles using simple text matching."""
        if self.df is None:
            raise ValueError("Model is not loaded. Call load_and_preprocess first.")
            
        clean_query = self._clean_title(query)
        if not clean_query:
            return pd.DataFrame()
            
        # Exact match
        exact_matches = self.df[self.df['clean_title'] == clean_query]
        if not exact_matches.empty:
            return exact_matches.head(top_n)
            
        # Starts with match
        starts_matches = self.df[self.df['clean_title'].str.startswith(clean_query, na=False)]
        if not starts_matches.empty:
            return starts_matches.head(top_n)
            
        # Contains match
        contains_matches = self.df[self.df['clean_title'].str.contains(clean_query, na=False)]
        return contains_matches.head(top_n)

    def recommend(self, title, type_filter=None, genre_filter=None, year_min=None, year_max=None, 
                  alpha=0.6, beta=0.2, gamma=0.2, top_n=10):
        """
        Generate hybrid recommendations based on Content Similarity, Popularity, and Bayesian Rating.
        
        alpha: Weight for Content Similarity (0.0 to 1.0)
        beta: Weight for Popularity (0.0 to 1.0)
        gamma: Weight for Rating (0.0 to 1.0)
        Note: alpha + beta + gamma = 1.0
        """
        if self.df is None:
            raise ValueError("Model is not loaded. Call load_and_preprocess first.")
            
        # Find matching item
        matches = self.search_titles(title, top_n=1)
        if matches.empty:
            return None, f"Title '{title}' not found."
            
        idx = matches.index[0]
        matched_item = self.df.loc[idx]
        
        # Calculate TF-IDF similarity
        query_vector = self.tfidf_matrix[idx]
        sim_scores = cosine_similarity(query_vector, self.tfidf_matrix).flatten()
        
        # Create a copy of the dataframe to calculate recommendations
        rec_df = self.df.copy()
        rec_df['similarity'] = sim_scores
        
        # Calculate Hybrid Score
        rec_df['hybrid_score'] = (
            alpha * rec_df['similarity'] + 
            beta * rec_df['normalized_popularity'] + 
            gamma * rec_df['normalized_rating']
        )
        
        # Exclude the input item itself
        rec_df = rec_df[rec_df.index != idx]
        
        # Apply filters
        if type_filter:
            rec_df = rec_df[rec_df['type'].str.lower() == type_filter.lower()]
            
        if genre_filter:
            rec_df = rec_df[rec_df['genres'].str.lower().str.contains(genre_filter.lower(), na=False)]
            
        if year_min is not None:
            rec_df = rec_df[rec_df['release_year'] >= year_min]
            
        if year_max is not None:
            rec_df = rec_df[rec_df['release_year'] <= year_max]
            
        # Sort by hybrid score
        rec_df = rec_df.sort_values(by='hybrid_score', ascending=False)
        
        # Select columns to return
        return_cols = [
            'show_id', 'type', 'title', 'director', 'cast', 'country', 
            'release_year', 'rating', 'genres', 'description', 
            'popularity', 'vote_count', 'vote_average', 'similarity', 'hybrid_score'
        ]
        
        return matched_item, rec_df[return_cols].head(top_n)
