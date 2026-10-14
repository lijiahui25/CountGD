# CountGD repository notes

- Keep exactly two files in `docs/`: `implement.md` for what the TPC-268 implementation changes relative to CountGD, and `experiment.md` for experimental protocol, commands, status, and results.
- For every repository code, configuration, data-protocol, or experiment change, review and update both documents in the same work. Record a dated note in each even when one document's substantive protocol stays unchanged.
- Record measured results only from actual logs or artifacts. Mark server status, commit, run ID, and metrics as unknown until verified; never turn planned results into measured results.
- Preserve comparability: a dataset exclusion, label policy, prompt, initialization, environment, or inference change needs its own recorded protocol and matching baseline.
