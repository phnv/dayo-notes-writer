def test_config_models_can_be_instantiated():
    from note_writer.domain.config.models import Config, BundleConfig, FrontmatterConfig

    config = Config(
        inputs={"clip": "clipboard"},
        templates={"daily": "templates/daily.md"},
        prompts={"clean": "prompts/clean.md"},
        storage={"inbox": "~/notes"},
        bundles={
            "daily": BundleConfig(
                template="daily",
                prompt="clean",
                storage="inbox"
            )
        },
        defaults={"bundle": "daily"},
        frontmatter=FrontmatterConfig(enabled=True, format="yaml"),
        options={"overwrite": False}
    )

    assert config.templates["daily"] == "templates/daily.md"
    assert config.bundles["daily"].storage == "inbox"
    assert config.frontmatter.enabled is True
