"""
Scheduler module for Career Automation & Stepcon Pipeline.
Features: F12 (Scheduling Architectures & Documentation)
"""

def __getattr__(name: str):
    if name in (
        "run_daily_job",
        "run_daily",
        "execute_combined_daily_run",
        "execute_candidate_career_workflow",
        "execute_stepcon_consultancy_workflow",
        "validate_cron_expression",
        "check_daily_idempotency",
        "record_dispatch",
    ):
        import scheduler.daily_dispatch as _dd
        return getattr(_dd, name)
    raise AttributeError(f"module 'scheduler' has no attribute '{name}'")

__all__ = [
    "run_daily_job",
    "run_daily",
    "execute_combined_daily_run",
    "execute_candidate_career_workflow",
    "execute_stepcon_consultancy_workflow",
    "validate_cron_expression",
    "check_daily_idempotency",
    "record_dispatch",
]
