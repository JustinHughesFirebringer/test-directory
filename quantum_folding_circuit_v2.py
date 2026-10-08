#!/usr/bin/env python3
"""Simulator-first quantum folding circuit experiment.

The circuit models recursive quantum folding as repeated, finite feedback
layers: each layer measures an echo qubit, conditionally folds a neighboring
state, and feeds that state into the next entangling layer. It uses structured
classical control so it can be transpiled for current IBM Quantum
dynamic-circuit backends without depending on a processor-specific layout.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister, transpile
from qiskit.qasm3 import dumps as qasm3_dumps
from qiskit.qpy import dump as qpy_dump
from qiskit.qpy import load as qpy_load
from qiskit_aer import AerSimulator


@dataclass(frozen=True)
class CircuitConfig:
    """Validated parameters for the folding circuit."""

    num_qubits: int = 5
    echo_point: int = 2
    fold_depth: int = 2

    def validate(self) -> None:
        if self.num_qubits < 3:
            raise ValueError("num_qubits must be at least 3")
        if not 0 <= self.echo_point < self.num_qubits:
            raise ValueError("echo_point must be a valid qubit index")
        if self.fold_depth < 1:
            raise ValueError("fold_depth must be positive")


def create_quantum_folding_circuit(
    num_qubits: int = 5, echo_point: int = 2, fold_depth: int = 2
) -> QuantumCircuit:
    """Build a finite recursive-folding experiment.

    Each fold layer measures the echo point and conditionally feeds a derived
    neighboring pair into the next layer. Targets are derived from the
    configuration rather than hard-coded, allowing the experiment to scale
    across backends.
    """

    config = CircuitConfig(num_qubits, echo_point, fold_depth)
    config.validate()

    qreg = QuantumRegister(config.num_qubits, "q")
    final = ClassicalRegister(config.num_qubits, "final")
    mid = ClassicalRegister(config.fold_depth, "mid")
    circuit = QuantumCircuit(qreg, final, mid, name="quantum_folding_v2")

    circuit.h(qreg)
    circuit.barrier(label="superposition")

    for source in range(config.num_qubits - 1):
        circuit.cx(qreg[source], qreg[source + 1])
    circuit.barrier(label="cascade")

    for layer in range(config.fold_depth):
        circuit.measure(qreg[config.echo_point], mid[layer])
        circuit.barrier(label=f"echo_measurement_{layer + 1}")

        feedback_target = (config.echo_point + 1 + layer) % config.num_qubits
        bridge = (config.echo_point + 2 + layer) % config.num_qubits
        with circuit.if_test((mid[layer], True)):
            circuit.x(qreg[feedback_target])
        circuit.barrier(label=f"classical_feedback_{layer + 1}")

        circuit.cx(qreg[feedback_target], qreg[bridge])
        circuit.h(qreg[bridge])
        circuit.barrier(label=f"refolding_{layer + 1}")

    interference_target = (config.echo_point + 1) % config.num_qubits
    if interference_target == 0:
        interference_target = 1
    circuit.cz(qreg[0], qreg[-1])
    circuit.h(qreg[0])
    circuit.cx(qreg[0], qreg[interference_target])
    circuit.barrier(label="interference")

    circuit.measure(qreg, final)
    return circuit


def run_on_simulator(circuit: QuantumCircuit, shots: int) -> dict[str, int]:
    """Execute the circuit locally with Aer and return final-register counts."""

    if shots < 1:
        raise ValueError("shots must be positive")
    simulator = AerSimulator()
    compiled = transpile(circuit, simulator, optimization_level=1)
    result = simulator.run(compiled, shots=shots).result()
    return normalize_counts(result.get_counts(), circuit.num_qubits)


def normalize_counts(counts: Mapping[Any, int], final_width: int | None = None) -> dict[str, int]:
    """Keep and validate the final-register portion of measurement keys.

    Qiskit renders multiple classical registers from right to left in counts
    keys. This circuit creates ``final`` before ``mid``, so the final register
    is the last space-separated segment. The width check makes a register-order
    change fail loudly instead of silently analyzing the mid-circuit record.
    """

    normalized: dict[str, int] = {}
    for key, value in counts.items():
        raw_key = str(key)
        segments = raw_key.split()
        bitstring = segments[-1] if len(segments) > 1 else raw_key.replace(" ", "")
        if final_width is not None and len(bitstring) != final_width:
            raise ValueError(
                f"Expected a {final_width}-bit final register, got {bitstring!r} "
                f"from counts key {raw_key!r}"
            )
        normalized[bitstring] = normalized.get(bitstring, 0) + int(value)
    return normalized


def load_runtime_service(token: str | None = None, instance: str | None = None) -> Any:
    """Create an IBM Quantum Runtime service without storing credentials."""

    from qiskit_ibm_runtime import QiskitRuntimeService

    token = token or os.getenv("IBM_QUANTUM_TOKEN") or os.getenv("IBMQ_CLOUD_API_KEY")
    instance = instance or os.getenv("IBM_QUANTUM_CRN")
    if token:
        arguments: dict[str, str] = {"channel": "ibm_cloud", "token": token}
        if instance:
            arguments["instance"] = instance
        return QiskitRuntimeService(**arguments)
    return QiskitRuntimeService()


def run_on_ibm(
    circuit: QuantumCircuit,
    backend_name: str,
    shots: int,
    token: str | None = None,
    instance: str | None = None,
) -> tuple[dict[str, int], str]:
    """Submit one circuit through SamplerV2 and return counts and job ID."""

    if shots < 1:
        raise ValueError("shots must be positive")

    from qiskit_ibm_runtime import SamplerV2

    service = load_runtime_service(token, instance)
    backend = service.backend(backend_name)
    operation_names = set(getattr(backend, "operation_names", ()))
    if operation_names and "if_else" not in operation_names:
        raise RuntimeError(
            f"Backend {backend_name} does not advertise if_else control flow; "
            "choose an IBM backend with dynamic-circuit support."
        )

    compiled = transpile(circuit, backend=backend, optimization_level=1)
    sampler = SamplerV2(mode=backend)
    job = sampler.run([compiled], shots=shots)
    result = job.result()
    counts = result[0].data.final.get_counts()
    return {str(key): int(value) for key, value in counts.items()}, job.job_id()


def analyze_counts(counts: Mapping[str, int]) -> dict[str, float | int | str]:
    """Calculate comparable statistics for Aer and SamplerV2 counts."""

    if not counts:
        raise ValueError("counts must not be empty")
    total = sum(int(value) for value in counts.values())
    if total <= 0:
        raise ValueError("counts must contain a positive number of shots")

    normalized = normalize_counts(counts)
    entropy = 0.0
    even_count = 0
    for bitstring, count in normalized.items():
        probability = count / total
        if probability > 0:
            entropy -= probability * math.log2(probability)
        if bitstring.count("1") % 2 == 0:
            even_count += count

    top_bitstring, top_count = max(normalized.items(), key=lambda item: item[1])
    return {
        "total_shots": total,
        "unique_bitstrings": len(normalized),
        "top_bitstring": top_bitstring,
        "top_probability": top_count / total,
        "entropy": entropy,
        "even_parity_probability": even_count / total,
    }


def save_circuit(circuit: QuantumCircuit, filename: Path) -> None:
    """Save a circuit in QPY format instead of unsafe general-purpose pickle."""

    filename.parent.mkdir(parents=True, exist_ok=True)
    with filename.open("wb") as stream:
        qpy_dump(circuit, stream)


def load_circuit(filename: Path) -> QuantumCircuit:
    """Load the first circuit from a QPY file."""

    with filename.open("rb") as stream:
        circuits = qpy_load(stream)
    if not circuits:
        raise ValueError(f"No circuit found in {filename}")
    return circuits[0]


def save_histogram(counts: Mapping[str, int], filename: Path) -> None:
    """Create an optional histogram without making plotting a hard dependency."""

    from qiskit.visualization import plot_histogram

    filename.parent.mkdir(parents=True, exist_ok=True)
    figure = plot_histogram(dict(counts), title="Quantum Folding Circuit v2")
    figure.savefig(filename)
    figure.clf()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shots", type=int, default=1024)
    parser.add_argument("--qubits", type=int, default=5)
    parser.add_argument("--echo", type=int, default=2)
    parser.add_argument("--fold-depth", type=int, default=2)
    parser.add_argument("--backend", help="IBM backend; omit to use local Aer")
    parser.add_argument("--token", help="IBM Quantum token; prefer environment or saved account")
    parser.add_argument("--instance", help="IBM Quantum CRN or service instance")
    parser.add_argument("--save-circuit", type=Path, metavar="FILE")
    parser.add_argument("--load-circuit", type=Path, metavar="FILE")
    parser.add_argument("--plot", type=Path, metavar="FILE")
    parser.add_argument("--qasm3", action="store_true", help="Print OpenQASM 3 and exit")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.load_circuit:
        circuit = load_circuit(args.load_circuit)
    else:
        circuit = create_quantum_folding_circuit(args.qubits, args.echo, args.fold_depth)

    if args.save_circuit:
        save_circuit(circuit, args.save_circuit)
    if args.qasm3:
        print(qasm3_dumps(circuit))
        return

    if args.backend:
        counts, job_id = run_on_ibm(
            circuit, args.backend, args.shots, args.token, args.instance
        )
        print(f"IBM Quantum job: {job_id}")
    else:
        counts = run_on_simulator(circuit, args.shots)
        print("Execution target: local Aer simulator")

    drawing = str(circuit.draw(output="text"))
    print(drawing.encode("ascii", "replace").decode("ascii"))
    print(json.dumps({"counts": counts, "analysis": analyze_counts(counts)}, indent=2))
    if args.plot:
        save_histogram(counts, args.plot)
        print(f"Histogram saved to {args.plot}")


if __name__ == "__main__":
    main()
