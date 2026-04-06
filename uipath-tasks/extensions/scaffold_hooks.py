"""Tasks scaffold hook — auto-enables persistence support.

When UiPath.Persistence.Activities is in project dependencies,
sets "supportsPersistence": true in project.json runtimeOptions.
"""


def enable_persistence_support(project_json):
    """Post-scaffold hook: enable persistence when Persistence.Activities present.

    Args:
        project_json: The project.json dict (modified in place).
    """
    all_deps = project_json.get("dependencies", {})
    if "UiPath.Persistence.Activities" in all_deps:
        if "runtimeOptions" in project_json:
            project_json["runtimeOptions"]["supportsPersistence"] = True
        else:
            project_json["runtimeOptions"] = {"supportsPersistence": True}
