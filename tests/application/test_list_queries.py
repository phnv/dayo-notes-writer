from note_writer.domain.config.models import Config
from note_writer.application.notes import list_templates, list_storages

def test_list_templates_returns_all_aliases():
    config = Config(templates={"weekly": "weekly.md", "meeting": "meeting.md"})
    assert list_templates(config) == ["weekly", "meeting"]

def test_list_storages_returns_all_aliases():
    config = Config(storage={"inbox": "/tmp/inbox", "reviews": "/tmp/reviews"})
    assert list_storages(config) == ["inbox", "reviews"]
