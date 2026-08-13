from app.main import _save_debug_upload, settings


def test_save_debug_upload_uses_configured_temporary_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "save_uploaded_images", True)
    monkeypatch.setattr(settings, "uploaded_images_path", str(tmp_path))

    saved = _save_debug_upload(b"demo-image", "image/png")

    assert saved is not None
    assert saved.parent == tmp_path
    assert saved.suffix == ".png"
    assert saved.read_bytes() == b"demo-image"


def test_save_debug_upload_can_be_disabled(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "save_uploaded_images", False)
    monkeypatch.setattr(settings, "uploaded_images_path", str(tmp_path))

    assert _save_debug_upload(b"demo-image", "image/png") is None
    assert list(tmp_path.iterdir()) == []
