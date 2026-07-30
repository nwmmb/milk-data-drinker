from timeless_downloader.cookies import (
    forget_cookie,
    remember_cookie,
    resolve_cookie,
    saved_cookie_exists,
)


def test_cookie_precedence(tmp_path):
    remember_cookie("saved=value", tmp_path)
    env = {"TIMELESS_COOKIE": "environment=value"}
    assert resolve_cookie("new=value", base_dir=tmp_path, environ=env) == (
        "new=value",
        "new",
    )
    assert resolve_cookie(base_dir=tmp_path, environ=env) == (
        "saved=value",
        "saved",
    )
    forget_cookie(tmp_path)
    assert resolve_cookie(base_dir=tmp_path, environ=env) == (
        "environment=value",
        "environment",
    )


def test_remember_status_and_forget(tmp_path):
    assert not saved_cookie_exists(tmp_path)
    path = remember_cookie(" secret=value ", tmp_path)
    assert saved_cookie_exists(tmp_path)
    assert path.read_text(encoding="utf-8") == "secret=value"
    assert forget_cookie(tmp_path)
    assert not saved_cookie_exists(tmp_path)
    assert not forget_cookie(tmp_path)
