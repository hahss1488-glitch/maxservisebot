from io import BytesIO

from PIL import Image

from services.avatar_service import (
    get_avatar_source,
    get_effective_avatar,
    invalidate_avatar_cache,
    reset_avatar,
    save_custom_avatar,
)


def test_save_custom_avatar_square(tmp_path, monkeypatch):
    from services import avatar_service as av

    monkeypatch.setattr(av.DatabaseManager, "set_custom_avatar", lambda user_id, path: None)
    img = Image.new("RGB", (800, 400), "red")
    b = BytesIO()
    img.save(b, format="PNG")
    out = save_custom_avatar(1, b.getvalue(), tmp_path)
    with Image.open(out) as saved:
        assert saved.size == (512, 512)


def test_replace_custom_avatar_changes_output(tmp_path, monkeypatch):
    from services import avatar_service as av

    saved_paths = []
    monkeypatch.setattr(av.DatabaseManager, "set_custom_avatar", lambda user_id, path: saved_paths.append(path))

    red = BytesIO()
    Image.new("RGB", (120, 120), "red").save(red, format="PNG")
    blue = BytesIO()
    Image.new("RGB", (120, 120), "blue").save(blue, format="PNG")

    p1 = save_custom_avatar(1, red.getvalue(), tmp_path)
    p2 = save_custom_avatar(1, blue.getvalue(), tmp_path)

    assert p1 != p2
    assert p2.exists()
    assert len(list(tmp_path.glob("1_*.jpg"))) == 1


def test_reset_avatar(monkeypatch, tmp_path):
    from services import avatar_service as av

    old = tmp_path / "1_old.jpg"
    old.write_bytes(b"x")
    monkeypatch.setattr(av.DatabaseManager, "get_avatar_settings", lambda user_id: {"custom_avatar_path": str(old), "avatar_source": "custom", "telegram_avatar_path": ""})
    monkeypatch.setattr(av.DatabaseManager, "reset_avatar_source", lambda user_id: None)
    monkeypatch.setattr(av, "get_avatar_source", lambda user_id: "default")
    assert reset_avatar(1, tmp_path) == "default"
    assert not old.exists()


def test_fallback_avatar_source(tmp_path, monkeypatch):
    from services import avatar_service as av

    tg = tmp_path / "tg.jpg"
    Image.new("RGB", (10, 10), "blue").save(tg)
    monkeypatch.setattr(
        av.DatabaseManager,
        "get_avatar_settings",
        lambda user_id: {"avatar_source": "custom", "custom_avatar_path": str(tmp_path / "missing.jpg"), "telegram_avatar_path": str(tg)},
    )
    assert get_avatar_source(1) == "telegram"
    assert get_effective_avatar(1) == str(tg)


def test_invalidate_avatar_cache(tmp_path):
    one = tmp_path / "7_a.jpg"
    two = tmp_path / "7_b.jpg"
    three = tmp_path / "8_a.jpg"
    one.write_bytes(b"1")
    two.write_bytes(b"2")
    three.write_bytes(b"3")
    invalidate_avatar_cache(7, tmp_path)
    assert not one.exists() and not two.exists()
    assert three.exists()
