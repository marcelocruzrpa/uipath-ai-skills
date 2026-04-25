"""validate_xaml package -- UiPath XAML validation and lint rules.

Preserves the import contract:
    from validate_xaml import validate_xaml_file, validate_project, auto_fix_file
"""

# Import lint modules in a specific order to populate _LINT_REGISTRY.
# The order below matches the original source file's decorator ordering.
# This is critical: lint rules execute in registration order.
from . import lints_data          # rules 2,3,4,6,7,8,15,17,19,20,21,29,31,32,35,48,51,57,58,72,92,104
from . import lints_ui            # rules 1,41,45,46,47,105,111,112
from . import lints_selectors     # rules 9,14,89,90,110
from . import lints_activities    # rules 11,12,13,27,34,36,37,38,49,50,52,53,54,55,56,60,76,79,80,98
from . import lints_hallucinations  # rules 17,22,23,25,30,33,70,71,73,78,83,85,86,88,91,103
from . import lints_variables     # rules 5,16,28,67,81,82
from . import lints_framework     # rules 39,59,62,63,64,65,66,68,69,74,75,77,100
from . import lints_types         # rules 18,24,40,87,93,95,99
from . import lints_version_compat  # rules 120,121,122

# Re-export the public API
from ._orchestration import validate_xaml_file, validate_project  # noqa: F401
from ._fixes import auto_fix_file  # noqa: F401
from ._cli import main  # noqa: F401
from ._context import ValidationResult, FileContext  # noqa: F401
from ._registry import lint_xaml_file  # noqa: F401
