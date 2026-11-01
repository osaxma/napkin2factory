"""Installed domains (FOUNDATION F1): the packages that register through the domain contract.

``INSTALLED`` lists them in installation order, which is the order every registry iterates
in (``core/registry.py``).  The core reads this list and never imports a domain by name.
Adding a domain: write its package (``docs/domains.md``) and add its module path here.
"""

from __future__ import annotations

#: Module paths of the installed domains, in installation order.
INSTALLED: tuple[str, ...] = ("napkin2factory.domains.mechanical",)
