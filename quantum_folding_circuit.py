#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Quantum Folding Circuit Implementation

This script implements a quantum folding circuit with mid-circuit measurement
and conditional operations, creating a recursive feedback loop in the quantum system.
The circuit demonstrates quantum-classical hybrid computation with echo points.
"""

import os
import sys
import pickle
import argparse
import datetime
import numpy as np
import matplotlib.pyplot as plt
from dotenv import load_dotenv

# Import Qiskit libraries
try:
    from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister, transpile
    from qiskit.circuit import Parameter
    from qiskit.algorithms.optimizers import SPSA
    from qiskit.primitives import Estimator
    from qiskit.visualization import plot_histogram
    from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2, Options
    from qiskit_ibm_runtime.exceptions import IBMInputValueError
    from qiskit.providers.aer import AerSimulator
except ImportError as e:
    print(f"Error: Required Qiskit package not found: {e}")
    print("Please install the required packages with:")
    print("    pip install qiskit qiskit-ibm-runtime qiskit-aer matplotlib python-dotenv")
    sys.exit(1)

def load_environment():
    """Load environment variables from .env file."""
    load_dotenv()
    
    api_key = os.getenv("IBMQ_CLOUD_API_KEY")
    if not api_key:
        print("Warning: IBMQ_CLOUD_API_KEY not found in environment variables")
    
    instance = os.getenv("IBM_QUANTUM_CRN")
    if not instance and api_key:
        print("Warning: IBM_QUANTUM_CRN not found but IBMQ_CLOUD_API_KEY is set")
        print("Using default instance")
    
    return {"api_key": api_key, "instance": instance}

def create_quantum_folding_circuit(num_qubits=5, echo_point=2):
    """
    Create a quantum folding circuit with mid-circuit measurement and conditional operations.
    
    Args:
        num_qubits: Number of qubits in the circuit (default: 5)
        echo_point: Index of the qubit to use as the echo point (default: 2)
        
    Returns:
        The quantum circuit object
    """
    # Step 1: Create quantum and classical registers
    qreg = QuantumRegister(num_qubits, 'q')
    creg = ClassicalRegister(num_qubits, 'c')
    qc = QuantumCircuit(qreg, creg)
    
    # Step 2: Superposition Encoding
    print("Applying superposition encoding...")
    for i in range(num_qubits):
        qc.h(qreg[i])  # Initialize superposition across all qubits
    
    qc.barrier()  # Visual separator in the circuit
    
    # Step 3: Cascade Entanglement (quantum folding begins)
    print("Creating cascade entanglement chain...")
    for i in range(num_qubits - 1):
        qc.cx(qreg[i], qreg[i+1])  # Cascade entanglement chain
    
    qc.barrier()  # Visual separator in the circuit
    
    # Step 4: Mid-circuit measurement to create echo point
    print(f"Creating mid-circuit echo point at qubit {echo_point}...")
    # Create a separate classical register for the mid-circuit measurement
    mid_creg = ClassicalRegister(1, 'mid')
    qc.add_register(mid_creg)
    
    # Measure the echo point qubit
    qc.measure(qreg[echo_point], mid_creg[0])
    
    qc.barrier()  # Visual separator in the circuit
    
    # Step 5: Conditional correction (folding echo feedback)
    print("Applying conditional correction based on echo point measurement...")
    # Apply X gate to qubit 3 if the echo point measurement is 1
    qc.x(qreg[3]).c_if(mid_creg, 1)
    
    qc.barrier()  # Visual separator in the circuit
    
    # Step 6: Re-entangle (recursive folding)
    print("Re-entangling qubits to create recursive folding...")
    qc.cx(qreg[3], qreg[1])
    qc.h(qreg[4])
    
    qc.barrier()  # Visual separator in the circuit
    
    # Step 7: Final Layer Interference Pattern
    print("Creating final layer interference pattern...")
    qc.cz(qreg[0], qreg[4])
    qc.h(qreg[0])
    qc.cx(qreg[0], qreg[1])
    
    qc.barrier()  # Visual separator in the circuit
    
    # Step 8: Final Measurement
    print("Performing final measurement...")
    qc.measure(qreg, creg)
    
    return qc

def optimize_circuit_parameters(circuit, backend=None, shots=1024):
    """
    Optimize the circuit parameters using SPSA.
    
    Args:
        circuit: The quantum circuit to optimize
        backend: The backend to run the circuit on (default: None, uses simulator)
        shots: Number of shots for each circuit execution
        
    Returns:
        The optimized parameters
    """
    print("Optimizing circuit parameters using SPSA...")
    
    # Create a parameterized version of the circuit
    param_circuit = QuantumCircuit(circuit.num_qubits)
    theta = Parameter('θ')
    phi = Parameter('φ')
    
    # Add parameterized gates
    for i in range(circuit.num_qubits):
        param_circuit.rx(theta, i)
        param_circuit.rz(phi, i)
    
    # Add the rest of the circuit
    param_circuit = param_circuit.compose(circuit)
    
    # Define the cost function to minimize
    def cost_function(params):
        bound_circuit = param_circuit.bind_parameters({theta: params[0], phi: params[1]})
        
        if backend is None:
            # Use simulator if no backend is provided
            simulator = AerSimulator()
            result = simulator.run(bound_circuit, shots=shots).result()
            counts = result.get_counts()
        else:
            # Use the provided backend
            options = Options()
            options.shots = shots
            sampler = SamplerV2(backend=backend, options=options)
            job = sampler.run(bound_circuit)
            result = job.result()
            counts = result.quasi_dists[0]
        
        # Calculate the cost based on the measurement results
        # Here we're trying to maximize the probability of the all-zeros state
        all_zeros = '0' * circuit.num_qubits
        cost = 1.0 - counts.get(all_zeros, 0) / shots
        return cost
    
    # Initialize the SPSA optimizer
    spsa = SPSA(maxiter=100)
    
    # Initial parameters
    initial_params = np.array([0.01, 0.01])
    
    # Run the optimization
    result = spsa.minimize(cost_function, initial_params)
    
    print(f"Optimization complete. Optimized parameters: {result.x}")
    return result.x

def save_circuit(circuit, filename="quantum_folding_circuit.pkl"):
    """
    Save the quantum circuit to a pickle file.
    
    Args:
        circuit: The quantum circuit to save
        filename: The filename to save to
    """
    print(f"Saving circuit to {filename}...")
    with open(filename, 'wb') as f:
        pickle.dump(circuit, f)
    print(f"Circuit saved to {filename}")

def load_circuit(filename="quantum_folding_circuit.pkl"):
    """
    Load a quantum circuit from a pickle file.
    
    Args:
        filename: The filename to load from
        
    Returns:
        The loaded quantum circuit
    """
    print(f"Loading circuit from {filename}...")
    with open(filename, 'rb') as f:
        circuit = pickle.load(f)
    print(f"Circuit loaded from {filename}")
    return circuit

def run_circuit_on_simulator(circuit, shots=8192):
    """
    Run the quantum circuit on the Aer simulator.
    
    Args:
        circuit: The quantum circuit to run
        shots: Number of shots
        
    Returns:
        The simulation results
    """
    print(f"Running circuit on simulator with {shots} shots...")
    simulator = AerSimulator()
    transpiled_circuit = transpile(circuit, simulator)
    result = simulator.run(transpiled_circuit, shots=shots).result()
    counts = result.get_counts()
    print("Simulation complete.")
    return counts

def submit_to_quantum_hardware(circuit, backend_name="ibm_sherbrooke", shots=8192, credentials=None):
    """
    Submit the quantum folding circuit to IBM Quantum hardware.
    
    Args:
        circuit: Quantum circuit to submit
        backend_name: Name of the backend to use
        shots: Number of shots to run
        credentials: Dictionary containing api_key and instance
        
    Returns:
        The job object if successful, None otherwise
    """
    print(f"Submitting circuit to {backend_name}...")
    
    if credentials is None:
        credentials = load_environment()
    
    api_key = credentials.get("api_key")
    instance = credentials.get("instance")
    
    if not api_key:
        print("Error: No API key provided. Cannot connect to IBM Quantum.")
        return None
    
    try:
        # Try to connect to IBM Quantum using cloud authentication
        service = QiskitRuntimeService(
            channel="ibm_cloud",
            token=api_key,
            instance=instance
        )
    except Exception as cloud_error:
        print(f"Cloud authentication failed: {cloud_error}")
        try:
            # Fall back to saved account
            print("Trying to use saved account...")
            service = QiskitRuntimeService()
        except Exception as saved_error:
            print(f"Saved account authentication failed: {saved_error}")
            print("Could not authenticate with IBM Quantum. Please check your credentials.")
            return None
    
    try:
        # Check if the requested backend is available
        backends = service.backends()
        backend_names = [b.name for b in backends]
        
        if backend_name not in backend_names:
            print(f"Backend {backend_name} not found. Available backends: {backend_names}")
            return None
        
        backend = service.backend(backend_name)
        
        # Configure the options for the sampler
        options = Options()
        options.shots = shots
        options.optimization_level = 1  # Use a moderate optimization level
        options.resilience_level = 1    # Basic error mitigation
        
        # Create a sampler
        sampler = SamplerV2(backend=backend, options=options)
        
        # Submit the job
        job = sampler.run(circuit)
        job_id = job.job_id()
        
        print(f"Job submitted successfully. Job ID: {job_id}")
        print(f"You can monitor the job status at: https://quantum.ibm.com/jobs/{job_id}")
        
        return job
    
    except Exception as e:
        print(f"Error submitting job: {e}")
        return None

def visualize_results(counts, title="Quantum Folding Circuit Results"):
    """
    Visualize the results of the quantum circuit execution.
    
    Args:
        counts: The measurement counts from the circuit execution
        title: The title for the plot
    """
    plt.figure(figsize=(12, 6))
    plot_histogram(counts, title=title)
    plt.tight_layout()
    
    # Save the figure to a file
    filename = f"quantum_folding_results_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    plt.savefig(filename)
    print(f"Results visualization saved to {filename}")
    
    # Show the plot
    plt.show()

def wait_for_job_completion(job, timeout=300):
    """
    Wait for the job to complete and return the results.
    
    Args:
        job: The job object
        timeout: Maximum time to wait in seconds
        
    Returns:
        The job results if successful, None otherwise
    """
    import time
    
    print(f"Waiting for job {job.job_id()} to complete (timeout: {timeout} seconds)...")
    
    start_time = time.time()
    while not job.done() and (time.time() - start_time) < timeout:
        remaining = timeout - (time.time() - start_time)
        print(f"Job status: {job.status()}. Waiting... ({remaining:.1f} seconds remaining)")
        time.sleep(10)
    
    if not job.done():
        print(f"Job did not complete within the timeout period ({timeout} seconds).")
        print(f"You can check the job status later at: https://quantum.ibm.com/jobs/{job.job_id()}")
        return None
    
    try:
        result = job.result()
        print("Job completed successfully!")
        return result
    except Exception as e:
        print(f"Error retrieving job results: {e}")
        return None

def analyze_results(result):
    """
    Analyze the results of the quantum circuit execution.
    
    Args:
        result: The result object from the job
        
    Returns:
        A dictionary containing the analysis results
    """
    print("Analyzing results...")
    
    if hasattr(result, 'get_counts'):
        # Result from simulator
        counts = result.get_counts()
    else:
        # Result from quantum hardware
        counts = result.quasi_dists[0]
    
    # Convert to a regular dictionary if needed
    if not isinstance(counts, dict):
        counts = dict(counts)
    
    # Calculate statistics
    total_shots = sum(counts.values())
    sorted_counts = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    
    # Calculate entropy
    entropy = 0
    for bitstring, count in counts.items():
        probability = count / total_shots
        if probability > 0:
            entropy -= probability * np.log2(probability)
    
    # Calculate parity
    even_parity_count = 0
    for bitstring, count in counts.items():
        # Count the number of 1s in the bitstring
        num_ones = sum(int(bit) for bit in bitstring)
        if num_ones % 2 == 0:
            even_parity_count += count
    even_parity_probability = even_parity_count / total_shots
    
    analysis = {
        "total_shots": total_shots,
        "unique_bitstrings": len(counts),
        "top_bitstring": sorted_counts[0][0],
        "top_probability": sorted_counts[0][1] / total_shots,
        "entropy": entropy,
        "even_parity_probability": even_parity_probability
    }
    
    print("Analysis complete:")
    for key, value in analysis.items():
        print(f"  {key}: {value}")
    
    return analysis

def main():
    """Main function to create and run the quantum folding circuit."""
    parser = argparse.ArgumentParser(description="Quantum Folding Circuit")
    parser.add_argument("--shots", type=int, default=8192, help="Number of shots")
    parser.add_argument("--qubits", type=int, default=5, help="Number of qubits")
    parser.add_argument("--echo", type=int, default=2, help="Echo point qubit index")
    parser.add_argument("--optimize", action="store_true", help="Optimize circuit parameters")
    parser.add_argument("--backend", type=str, default=None, help="Backend to use (default: simulator)")
    parser.add_argument("--save", action="store_true", help="Save the circuit")
    parser.add_argument("--load", type=str, default=None, help="Load circuit from file")
    args = parser.parse_args()
    
    # Load or create the circuit
    if args.load:
        circuit = load_circuit(args.load)
    else:
        circuit = create_quantum_folding_circuit(args.qubits, args.echo)
        print(f"Created quantum folding circuit with {args.qubits} qubits and echo point at qubit {args.echo}")
    
    # Save the circuit if requested
    if args.save:
        save_circuit(circuit)
    
    # Optimize the circuit if requested
    if args.optimize:
        params = optimize_circuit_parameters(circuit, shots=args.shots)
        # You could use these parameters to modify the circuit if desired
    
    # Draw the circuit
    print("Circuit diagram:")
    print(circuit.draw(output='text'))
    
    # Run the circuit on the simulator or hardware
    if args.backend:
        # Submit to quantum hardware
        credentials = load_environment()
        job = submit_to_quantum_hardware(circuit, args.backend, args.shots, credentials)
        
        if job:
            # Wait for the job to complete
            result = wait_for_job_completion(job)
            
            if result:
                # Analyze and visualize the results
                analysis = analyze_results(result)
                visualize_results(result.quasi_dists[0], f"Quantum Folding Circuit Results - {args.backend}")
        else:
            print("Running on simulator instead...")
            counts = run_circuit_on_simulator(circuit, args.shots)
            analyze_results(counts)
            visualize_results(counts, "Quantum Folding Circuit Results - Simulator")
    else:
        # Run on simulator
        counts = run_circuit_on_simulator(circuit, args.shots)
        analyze_results(counts)
        visualize_results(counts, "Quantum Folding Circuit Results - Simulator")

if __name__ == "__main__":
    main()
