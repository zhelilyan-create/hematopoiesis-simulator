"""Simulation observers.

Observers are called by CTMCEngine after every event and record or
react to changes in the population without coupling to the engine's
core logic.

Extension path
--------------
- Add on_division() / on_apoptosis() hooks for fine-grained event logging.
- Implement a LivePlotter observer for real-time visualisation.
- Implement a CheckpointWriter for long runs.
"""
