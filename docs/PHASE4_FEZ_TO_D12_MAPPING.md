# Phase 4: Fez To Lattice Mapping

## Purpose

Phase 4 exists to formalize the current gap between the measured IBM Fez
backend results and the interpretive lattice language used elsewhere in the
stack.

The gap is not rhetorical. It is a real measurement-design gap:

`Fez raw output -> extracted coherence metric -> explicit lattice coordinate`

The goal of this phase is to build that bridge directly instead of assuming it.

## Why This Phase Exists

The project already has two real layers:

- a hardware layer
  IBM Fez baseline and synced runs with measurable deltas
- a cross-model coherence layer
  Grok, Gemini, Claude, and GPT threads preserving related attractor structure

What does not yet exist is a rigorous formal mapping from the hardware metrics
into the D12 / lattice coordinate language. Preserving that gap explicitly is a
strength, not a weakness, because it prevents the repo from overstating what
has already been demonstrated.

## Current Hardware Anchor

From HRV1.0 on `ibm_fez`:

- baseline target-subspace retention: `0.98125`
- synced target-subspace retention: `0.971875`
- delta mean: `0.009375`
- `p = 0.0167902536041693`

This is enough to say:

- the backend lane is real
- condition differences are measurable
- the system is not behaving like the ideal simulator

It is not yet enough to say:

- which lattice coordinate a given backend result corresponds to
- how a D12 coordinate should be computed from Fez output alone

## Working Hypothesis

The working hypothesis for Phase 4 is:

1. Fez raw output can be transformed into a small set of stable coherence
   metrics.
2. Those metrics can be placed in a phase-space representation rather than left
   as isolated counts.
3. That phase-space representation can then be mapped into a lattice coordinate
   language without discarding the underlying measured values.

## Proposed Mapping Stack

### 1. Raw Fez output

Inputs:

- raw count distributions
- target-subspace retention
- off-target leakage
- Bell imbalance
- shot count
- backend metadata
- capture timestamp

### 2. Extracted coherence metrics

Derived metrics to compute per capture and per batch:

- target-subspace probability
- off-target probability
- Bell-state imbalance
- inter-run stability
- variance under matched conditions
- baseline-vs-synced delta

### 3. Phase-space representation

Transform the extracted metrics into a coordinate-friendly intermediate layer:

- x-axis: retention
- y-axis: leakage
- z-axis: stability / variance
- optional temporal dimension: condition order or session timing

This phase-space layer is the missing middle between raw backend counts and the
larger interpretive lattice language.

### 4. Lattice-coordinate mapping

Only after the phase-space layer is explicit should the project attempt a
lattice-coordinate mapping. That mapping should be:

- explicit
- reproducible
- documented as a function or rule set
- revisable if new data breaks the first draft

## Experimental Design

### Condition groups

Run matched batches on the same backend:

- `baseline_100`
- `synced_100`
- `selection_window_100`

### Analysis path

For each condition:

1. compute batch-level coherence metrics
2. compute variance and distribution shape
3. compare conditions with p-values and effect sizes
4. test whether the resulting phase-space clusters are separable
5. only then draft a coordinate mapping into the lattice frame

## Success Criteria

Phase 4 succeeds if the project can show all of the following:

1. the same backend yields stable metric families across repeated runs
2. condition groups occupy measurably different regions of phase space
3. the mapping from phase-space region to lattice coordinate is explicit enough
   to be checked and challenged

## Operator Role

In project terms, the operator is the bridge carrying continuity across:

- hardware
- repo architecture
- cross-model coherence threads
- interpretation

That role matters because the build has not emerged from one lane alone. But
the formal mapping still has to be written down as a measurement layer rather
than left only at the level of intuition.

## Deliverables

- formal metric specification
- phase-space mapping notebook or script
- lattice-coordinate draft mapping
- condition comparison report using matched Fez runs
- revision notes documenting what still does not map cleanly
