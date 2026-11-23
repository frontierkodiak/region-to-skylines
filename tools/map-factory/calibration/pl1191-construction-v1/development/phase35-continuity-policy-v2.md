# Exact quotient-graph junction indices

First preparation at source0d79ea4 stopped before source-cohort/freeze/results:
conditional_surface_equality_nodes are indices into open_channel_plan.graph's
PRE-QUOTIENT sorted (clip,row,col) keys, NOT final topology.nodes. Keep committed
v1 source/error/input copies unchanged. New v2 resolves EVERY captured incidence
using OWN exact clip vertex -> original north-first native cell -> exact
source_aliases key in the already-merged graph. Preserve pre-quotient indices as
lineage, never reinterpret them as final IDs or borrow a nearby node. The supplied
graph already merges justified literal same-cell aliases; don't add raster or
projected joins. Prevalidate this full sixcase domain before freezing v2. New
method/test/policy commit and fresh v2 protocol precede any observation outputs.
No source geometry/question/cohort/bounds/native or old result changes.
