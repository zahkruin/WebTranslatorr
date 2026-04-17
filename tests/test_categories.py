"""
Tests for CategoryMapper.
"""

import pytest
from app.core.categories import CategoryMapper


def test_is_book_category():
    assert CategoryMapper.is_book_category(7000) is True
    assert CategoryMapper.is_book_category(7020) is True
    assert CategoryMapper.is_book_category(8010) is True
    assert CategoryMapper.is_book_category(2000) is False
    assert CategoryMapper.is_book_category(5000) is False


def test_is_movie_category():
    assert CategoryMapper.is_movie_category(2000) is True
    assert CategoryMapper.is_movie_category(2040) is True
    assert CategoryMapper.is_movie_category(7000) is False
    assert CategoryMapper.is_movie_category(5000) is False


def test_is_tv_category():
    assert CategoryMapper.is_tv_category(5000) is True
    assert CategoryMapper.is_tv_category(5040) is True
    assert CategoryMapper.is_tv_category(2000) is False
    assert CategoryMapper.is_tv_category(7000) is False


def test_categorize_request():
    assert CategoryMapper.categorize_request([7000, 7020]) == {"books"}
    assert CategoryMapper.categorize_request([2000, 2040]) == {"movies"}
    assert CategoryMapper.categorize_request([5000, 5040]) == {"tv"}
    assert CategoryMapper.categorize_request([7000, 2000]) == {"books", "movies"}
    assert CategoryMapper.categorize_request([]) == {"books", "movies", "tv"}


def test_get_parent_category():
    assert CategoryMapper.get_parent_category(7020) == 7000
    assert CategoryMapper.get_parent_category(2040) == 2000
    assert CategoryMapper.get_parent_category(5040) == 5000
