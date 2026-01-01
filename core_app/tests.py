import pytest


def test_basic_math():
    
    assert 1 + 1 == 2

@pytest.mark.django_db
def test_database_access():
  
    pass
