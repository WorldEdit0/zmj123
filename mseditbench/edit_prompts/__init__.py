"""Edit prompt generation: T1-T7.

    from mseditbench.edit_prompts.tasks import ALL_TASKS
    from mseditbench.edit_prompts.generate import generate_for_task

CLI: python -m mseditbench.edit_prompts.generate --help
"""

from .tasks import ALL_TASKS
from .generate import generate_for_task, SAMPLERS

__all__ = ["ALL_TASKS", "generate_for_task", "SAMPLERS"]
