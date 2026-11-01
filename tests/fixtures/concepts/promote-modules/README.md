# promote-modules

One concept card with modules (v0.4 M5, P10), promoted into a fresh `n2f init` product (the
blank template, no assembly) by `tests/unit/test_promote_modules.py`. The goldens next door,
`promote-modules-golden/`, are the assembly files and `requirements.yaml` that promotion
writes; regenerate with `N2F_PROMOTE_GOLDEN=1` after an intended change and review the diff.
