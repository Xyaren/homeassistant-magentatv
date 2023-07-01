from custom_components.magentatv.api.utils import magneta_hash


def test_hash_function():
    assert magneta_hash("Test") == "0CBC6611F5540BD0809A388DC95A615B"
