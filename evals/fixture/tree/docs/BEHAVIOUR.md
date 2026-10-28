# tally behaviour map

Each entry is one line the user would recognise, **every surface** it appears on, and the test that guards it, or **untested**.

## Surfaces

| Code | Surface |
| --- | --- |
| **CLI** | the `tally` command |
| **LIB** | `tally.core` called from Python |

## 1. Arithmetic

| Behaviour | Surfaces | Guarded by |
| --- | --- | --- |
| **AR-01** The total of the numbers is shown. | CLI LIB | `tests/test_core.py::TestCore::test_total`, `tests/test_cli.py::TestCli` |
| **AR-02** The average of the numbers is shown. | CLI LIB | `tests/test_core.py::TestCore::test_average` |
| **AR-03** The top N numbers can be listed. | LIB | `tests/test_core.py::TestCore::test_top` |

## Escapes

Every bug found after a release gets one line here, in the fix's commit, and that commit adds the check named: "#NN (vX.Y.Z): should have been caught by <check>; added <test / map entry / release-gate case>".

## Harness escapes

A process rule broken by a session (not a bug in the product) gets one line here: what happened, and the hook case or permission rule that now stops it.

---

## Untested: backlog
