# Additive authored-entry reader correction

The frozen v1 evaluator stopped on its first case before writing any case JSON:
original authored-control/plan inventory entries have no geographic `field`.
Preserve v1 freeze, all251boundsourcebytes, empty output directory and raw error.
This v2 reader separates captured body-domain rows from fieldless authored-plan
rows. Natural controls are NOT mapped polygon interiors and their names do not
establish source ownership. Unsupported entries remain explicit unknown sites.
No source/contract is omitted, no control reassigned, no bounds/protection/geometry
or design question changes. Add a focused behavioral reader test. Commit before
fresh v2 inputfreeze/outputs; never edit/reuse the v1 protocol with new code.
