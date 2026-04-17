"""
Mapeo completo de categorías Newznab estándar.
"""


class CategoryMapper:
    # Categorías padre
    MOVIES = 2000
    TV = 5000
    BOOKS = 7000
    BOOKS_ALT = 8000

    # Subcategorías de libros
    BOOK_EBOOK = 7020
    BOOK_EBOOK_ALT = 8010
    BOOK_COMICS = 7030
    BOOK_COMICS_ALT = 8020
    BOOK_MAGAZINES = 7040
    BOOK_MAGAZINES_ALT = 8030

    # Subcategorías de películas
    MOVIE_FOREIGN = 2010
    MOVIE_SD = 2030
    MOVIE_HD = 2040
    MOVIE_UHD = 2045
    MOVIE_BLURAY = 2050
    MOVIE_WEBDL = 2080

    # Subcategorías de TV
    TV_WEBDL = 5010
    TV_FOREIGN = 5020
    TV_SD = 5030
    TV_HD = 5040
    TV_UHD = 5045
    TV_ANIME = 5070

    # Rangos por tipo de contenido
    BOOK_RANGE = range(7000, 8999)
    MOVIE_RANGE = range(2000, 2999)
    TV_RANGE = range(5000, 5999)
    VIDEO_RANGE = range(2000, 5999)

    # Book categories list
    ALL_BOOK_CATEGORIES = [7000, 7020, 8000, 8010, 7030, 8020, 7040, 8030]

    @classmethod
    def is_book_category(cls, cat_id: int) -> bool:
        return cat_id in cls.BOOK_RANGE

    @classmethod
    def is_video_category(cls, cat_id: int) -> bool:
        return cat_id in cls.MOVIE_RANGE or cat_id in cls.TV_RANGE

    @classmethod
    def is_movie_category(cls, cat_id: int) -> bool:
        return cat_id in cls.MOVIE_RANGE

    @classmethod
    def is_tv_category(cls, cat_id: int) -> bool:
        return cat_id in cls.TV_RANGE

    @classmethod
    def get_parent_category(cls, cat_id: int) -> int:
        return (cat_id // 1000) * 1000

    @classmethod
    def normalize_categories(cls, cats: list[int]) -> list[int]:
        """Normaliza lista de categorías, removiendo duplicados."""
        return list(set(cats))

    @classmethod
    def categorize_request(cls, categories: list[int]) -> set[str]:
        """Devuelve un set con los tipos: {'books', 'movies', 'tv'}"""
        types = set()
        for cat in categories:
            if cls.is_book_category(cat):
                types.add("books")
            elif cat in cls.MOVIE_RANGE:
                types.add("movies")
            elif cat in cls.TV_RANGE:
                types.add("tv")
        return types if types else {"books", "movies", "tv"}
