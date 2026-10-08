# Quantum experiments

This directory contains experimental quantum-circuit designs. The central aim is to generate **recursive quantum folding**: a finite sequence of echo measurements and conditional feedback layers in which each fold feeds a transformed state into the next entangling layer. The experiment explores cascade entanglement, mid-circuit measurement, classical feedback, and a final interference layer.

Here, “recursive” describes repeated quantum-circuit feedback stages, not unbounded recursion in Python. The v2 implementation exposes the number of stages as `--fold-depth` so the depth/noise trade-off can be measured explicitly.

## Files

- [`quantum_folding_circuit.py`](quantum_folding_circuit.py) — original prototype.
- [`quantum_folding_circuit_v2.py`](quantum_folding_circuit_v2.py) — simulator-first refactor for current Qiskit APIs and IBM Quantum dynamic-circuit backends.

## Setup

Use a dedicated environment for the quantum experiment rather than the parent directory's steganography dependencies. Install current compatible packages from the package index:

```text
python -m pip install --upgrade qiskit qiskit-aer qiskit-ibm-runtime
```

Matplotlib is optional and is only needed for `--plot`:

```text
python -m pip install --upgrade matplotlib
```

## Run locally

The default target is the local Aer simulator:

```text
python quantum_folding_circuit_v2.py --shots 1024
```

The circuit size and echo qubit can be changed. The echo index must be within the selected register, and at least three qubits are required:

```text
python quantum_folding_circuit_v2.py --qubits 7 --echo 3 --fold-depth 3 --shots 2048
```

To save a circuit in QPY format, print OpenQASM 3, or save a histogram:

```text
python quantum_folding_circuit_v2.py --save-circuit artifacts/folding.qpy
python quantum_folding_circuit_v2.py --qasm3
python quantum_folding_circuit_v2.py --plot artifacts/folding.png
```

QPY is used instead of Python pickle because loading an untrusted pickle can execute arbitrary code.

## IBM Quantum hardware

The v2 circuit is intentionally small and topology-independent so Qiskit can transpile it for the selected backend. It implements a configurable number of mid-circuit measurements and structured `if_test` conditional feedback blocks, controlled by `--fold-depth`. The default configuration uses two folding stages rather than relying on a hard-coded qubit layout or legacy `.c_if()` calls.

IBM Quantum Heron R2/R3 and Nighthawk systems are dynamic-circuit-capable processor families, but the exact backend availability, supported instructions, queue status, and control-flow constraints can vary by backend and over time. The script therefore does not hard-code a Heron or Nighthawk backend name. Select an available backend from your IBM Quantum account and let the backend-aware transpiler map the circuit:

```text
python quantum_folding_circuit_v2.py --backend YOUR_BACKEND --shots 1024
```

Before hardware execution:

1. Confirm that the selected backend currently supports dynamic circuits and conditional control flow.
2. Keep the experiment shallow; mid-circuit measurement and classical feedback add latency and are affected by measurement/reset and feed-forward error.
3. Start with a small shot count and inspect the transpiled circuit before scaling up.
4. Do not put tokens in source files or commit `.env` files.

Authenticate using a saved Qiskit Runtime account, or provide credentials through environment variables supported by the script:

```text
set IBM_QUANTUM_TOKEN=your-token
set IBM_QUANTUM_CRN=your-instance-crn
python quantum_folding_circuit_v2.py --backend YOUR_BACKEND
```

A saved account is preferred for normal use. The script also accepts `--token` and `--instance`, but shell history and process inspection can expose command-line secrets.

## V2 design notes

- Circuit construction validates qubit, echo-point, and recursive fold-depth configuration.
- Each fold layer measures the echo point, conditionally applies feedback, and re-entangles a derived neighboring pair.
- Feedback, bridge, and interference qubits are derived from the configuration instead of being fixed at `q[3]` and `q[4]`.
- Aer and IBM Runtime results are normalized to the same counts representation before analysis.
- `SamplerV2` is used for IBM execution, and the result is read from the measured `final` register.
- Hardware execution is opt-in; local simulation remains the default.
- The refactor avoids the removed `qiskit.algorithms` and `qiskit.providers.aer` imports used by the original prototype.

## Provenance

This experiment originated as `quantum_folding_circuit.py`, an exploratory upload to the repository before the quantum work was organized into its own directory. The historical GitHub blob associated with that original upload is `0034db09a154865c1e7771e939365f98534cd03d`. `quantum_folding_circuit_v2.py` is an explicit refactor of that prototype: it preserves the original cascade/echo/feedback concept while making recursive folding depth configurable, modernizing Qiskit APIs, and adding simulator-first execution. The circuit design and implementation in this directory are experimental and are not presented as a benchmark or a claim of a quantum advantage. No third-party source attribution has been independently verified from the local project history; add attribution here if the original implementation incorporated external examples.

## License

Copyright (c) 2026 Justin Hughes.

The quantum experiments are released under the **MIT License**. The license permits use, copying, modification, publication, distribution, sublicensing, and sale, subject to inclusion of the copyright and permission notices. The complete legal text is available in the repository-level [`LICENSE`](../LICENSE) file. The MIT License applies to my original contributions in both quantum_folding_circuit.py, including the recorded historical Git blob 0034db09a154865c1e7771e939365f98534cd03d, and quantum_folding_circuit_v2.py. Third-party materials, if present, remain subject to their respective licenses.
