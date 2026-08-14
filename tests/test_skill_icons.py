from pathlib import Path

from toram_search.skill_icons import SkillIconCatalog, normalize_icon_key


def test_normalize_icon_key_ignores_case_space_and_punctuation() -> None:
    assert normalize_icon_key("Shield: Bash!") == "shieldbash"


def test_catalog_resolves_tree_local_icon(tmp_path: Path) -> None:
    root = tmp_path / "icons"
    folder = root / "Shield"
    folder.mkdir(parents=True)
    icon = folder / "Guardian.png"
    icon.write_bytes(b"png")

    catalog = SkillIconCatalog(root)

    assert catalog.resolve("Shield Skills", "Guardian") == icon.resolve()


def test_catalog_applies_existing_tree_folder_aliases(tmp_path: Path) -> None:
    root = tmp_path / "icons"
    folder = root / "MagicBlade"
    folder.mkdir(parents=True)
    icon = folder / "Magic: Finale.png"
    icon.write_bytes(b"png")

    catalog = SkillIconCatalog(root)

    assert catalog.resolve("Magic Warrior Skills", "Magic Finale") == icon.resolve()


def test_catalog_uses_unique_global_fallback(tmp_path: Path) -> None:
    root = tmp_path / "icons"
    folder = root / "Other"
    folder.mkdir(parents=True)
    icon = folder / "Guardian.png"
    icon.write_bytes(b"png")

    catalog = SkillIconCatalog(root)

    assert catalog.resolve("Unknown Skills", "Guardian") == icon.resolve()


def test_catalog_refuses_ambiguous_global_fallback(tmp_path: Path) -> None:
    root = tmp_path / "icons"
    for folder_name in ("One", "Two"):
        folder = root / folder_name
        folder.mkdir(parents=True)
        (folder / "Duplicate.png").write_bytes(b"png")

    catalog = SkillIconCatalog(root)

    assert catalog.resolve("Missing Skills", "Duplicate") is None


def test_real_guardian_icon_is_checked_in() -> None:
    catalog = SkillIconCatalog(Path("coryn_skill_icons"))
    icon = catalog.resolve("Shield Skills", "Guardian")

    assert icon is not None
    assert icon.name == "Guardian.png"
    assert icon.is_file()
