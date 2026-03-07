import sys
from textwrap import dedent

from api.blueprint_loader import discover_blueprints


def test_discover_blueprints_loads_router_modules(tmp_path):
    package_root = tmp_path / "samplepkg"
    feature_dir = package_root / "feature"
    feature_dir.mkdir(parents=True)

    (package_root / "__init__.py").write_text("", encoding="utf-8")
    (feature_dir / "__init__.py").write_text("", encoding="utf-8")
    (feature_dir / "router.py").write_text(
        dedent(
            """
            from flask import Blueprint

            bp = Blueprint("feature_default", __name__)
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    (feature_dir / "router_v2.py").write_text(
        dedent(
            """
            from flask import Blueprint

            blueprints = [Blueprint("feature_v2", __name__)]
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    sys.path.insert(0, str(tmp_path))
    try:
        blueprints = discover_blueprints(package_name="samplepkg")
    finally:
        sys.path.remove(str(tmp_path))
        for module_name in list(sys.modules):
            if module_name == "samplepkg" or module_name.startswith("samplepkg."):
                sys.modules.pop(module_name, None)

    assert [blueprint.name for blueprint in blueprints] == ["feature_default", "feature_v2"]
