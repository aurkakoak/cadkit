# cq_warehouse fasteners

Source: https://github.com/gumyr/cq_warehouse

Revision: `daa46507ecc429c0e2dce11d9d5ffd09b12a42af`

Copyright 2021 Gumyr. Distributed under Apache-2.0; see `LICENSE`.
The upstream revision has no NOTICE file.

CadKit bundles `fastener.py`, `thread.py`, and every CSV file referenced by
`fastener.py`. The upstream copyright and licence headers are retained.
`__init__.py` is a CadKit stub. The only changes to the upstream modules are
in `fastener.py`: the thread import and CSV resource lookup use this private
package instead of the top-level `cq_warehouse` package. `thread.py` and the
CSV files are unchanged. No CadQuery extension monkey patches are loaded.

To update, obtain the chosen upstream revision, copy these two modules and
all CSV files named in `fastener.py`, apply the same private import/resource
changes, and copy its licence and any NOTICE file. Update this revision and
`PROVIDER_REVISION` in `cadkit/fasteners.py` together. Run the mechanics tests
and `scripts/check_distribution.py` against both built distributions to check
geometry, data files, and installation without the upstream Git dependency.
