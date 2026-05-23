"""External-system clients and persistence layer.

Every service is async, takes config at construction, and exposes a tight
interface. No service depends on Flet or on another service's internal state.
"""
