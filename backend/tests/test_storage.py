from concurrent.futures import ThreadPoolExecutor

from service import storage


def test_json_store_upsert_preserves_concurrent_keys(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "STORAGE_DIR", tmp_path)
    store = storage.JsonStore("concurrent.json")

    def write_item(index):
        key = f"key_{index}"
        store.upsert(key, {"index": index})

    with ThreadPoolExecutor(max_workers=12) as executor:
        list(executor.map(write_item, range(60)))

    data = store.read()
    assert len(data) == 60
    assert data["key_0"]["index"] == 0
    assert data["key_59"]["index"] == 59
