# NEWLY ADDED
import pytest

from asgiref.local import Local


def test_delattr_missing_raises():
    local = Local()
    with pytest.raises(AttributeError, match="no attribute"):
        del local.never_set


def test_delattr_after_delete_raises():
    local = Local()
    local.foo = 1
    del local.foo
    with pytest.raises(AttributeError, match="no attribute"):
        del local.foo
