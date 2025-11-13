from pytket.circuit import Circuit, OpType
from pytket.qasm import circuit_to_qasm_str
from pytket.transform import Transform
import random

def generate_ghz(n_qubits: int) -> str:
    """Generates a GHZ state circuit (Entanglement)."""
    if n_qubits < 2:
        raise ValueError("GHZ state requires at least 2 qubits.")
    
    circ = Circuit(n_qubits)
    circ.H(0)
    for i in range(n_qubits - 1):
        circ.CX(i, i + 1)
    
    return circuit_to_qasm_str(circ)

def generate_bell_state(n_qubits: int) -> str:
    """Generates a Bell State on the first two qubits (ignores n > 2)."""
    # We accept n_qubits to keep the API consistent, but we only use 2.
    if n_qubits < 2:
        raise ValueError("Bell state requires at least 2 qubits.")
        
    circ = Circuit(n_qubits)
    circ.H(0)
    circ.CX(0, 1)
    
    return circuit_to_qasm_str(circ)

def generate_qft(n_qubits: int) -> str:
    """Generates a Quantum Fourier Transform circuit."""
    if n_qubits < 1:
        raise ValueError("QFT requires at least 1 qubit.")
        
    circ = Circuit(n_qubits)
    
    # Main QFT logic
    for i in range(n_qubits):
        circ.H(i)
        for j in range(i + 1, n_qubits):
            # Angle is in half-turns (1 = pi, 0.5 = pi/2)
            angle = 1 / (2**(j - i))
            circ.CU1(angle, j, i)
        circ.add_barrier(range(n_qubits))
            
    # SWAP network to reverse qubit order
    for i in range(n_qubits // 2):
        circ.SWAP(i, n_qubits - 1 - i)
        
    return circuit_to_qasm_str(circ)

def generate_grover_search(n_qubits: int) -> str:
    """Generates a simplified Grover search circuit with strict gate decomposition."""
    if n_qubits < 2:
        raise ValueError("Grover search requires at least 2 qubits.")
        
    circ = Circuit(n_qubits)
    
    # 1. Superposition
    for i in range(n_qubits):
        circ.H(i)
        
    # 2. Dummy Oracle (marks the |11...1> state)
    for i in range(n_qubits):
        circ.X(i)
    
    # Multi-controlled X (MCX) logic
    controls = list(range(n_qubits - 1))
    circ.H(n_qubits - 1)
    circ.add_gate(OpType.CnX, controls + [n_qubits - 1])
    circ.H(n_qubits - 1)
    
    for i in range(n_qubits):
        circ.X(i)
        
    # 3. Diffuser
    for i in range(n_qubits):
        circ.H(i)
        circ.X(i)
        
    circ.H(n_qubits - 1)
    circ.add_gate(OpType.CnX, controls + [n_qubits - 1])
    circ.H(n_qubits - 1)
    
    for i in range(n_qubits):
        circ.X(i)
        circ.H(i)
    
    # --- FIX: Strict Decomposition ---
    # 1. Break down large CnX gates into simpler CnX (e.g., 3-qubit CCX)
    Transform.CnXPairwiseDecomposition().apply(circ)
    # 2. Break down any remaining CCX gates into CX and single-qubit gates
    Transform.DecomposeCCX().apply(circ)
    # ---------------------------------
        
    return circuit_to_qasm_str(circ)

def generate_bernstein_vazirani(n_qubits: int) -> str:
    """
    Generates a Bernstein-Vazirani circuit.
    We encode the 'all-ones' string '11...1' as the secret key
    because this creates the maximum number of CNOT gates (worst case).
    """
    if n_qubits < 2:
        raise ValueError("BV requires at least 2 qubits.")
    
    circ = Circuit(n_qubits)
    target = n_qubits - 1
    
    # Initialize inputs to |+> and target to |->
    for i in range(target):
        circ.H(i)
    
    circ.X(target)
    circ.H(target)
    
    # Barrier for visual clarity
    circ.add_barrier(range(n_qubits))
    
    # Oracle for secret string "11...1"
    # Apply CNOT from every input bit to the target bit
    for i in range(target):
        circ.CX(i, target)
        
    circ.add_barrier(range(n_qubits))
        
    # Final Hadamard layer
    for i in range(target):
        circ.H(i)
        
    return circuit_to_qasm_str(circ)

def generate_vqe_ansatz(n_qubits: int) -> str:
    """
    Generates a 'Hardware Efficient Ansatz' often used in VQE.
    It consists of layers of single-qubit rotations and entangling gates.
    Good for testing raw floating-point performance.
    """
    if n_qubits < 2:
        raise ValueError("VQE Ansatz requires at least 2 qubits.")
        
    circ = Circuit(n_qubits)
    
    # Layer 1: Ry Rotations (Arbitrary angle 0.5 half-turns)
    for i in range(n_qubits):
        circ.Ry(0.5, i)
        
    # Layer 2: Entanglement (Chain of CNOTs)
    for i in range(n_qubits - 1):
        circ.CX(i, i + 1)
        
    # Layer 3: Rx Rotations
    for i in range(n_qubits):
        circ.Rx(0.5, i)
        
    return circuit_to_qasm_str(circ)

def generate_random_circuit(n_qubits: int) -> str:
    """
    Generates a random circuit of depth = n_qubits.
    This is useful for 'Chaos' testing to defeat compiler optimizations.
    """
    if n_qubits < 2:
        raise ValueError("Random circuit requires at least 2 qubits.")
        
    circ = Circuit(n_qubits)
    depth = n_qubits  # Linear depth
    
    for _ in range(depth):
        # Random single qubit rotation
        q = random.randint(0, n_qubits - 1)
        circ.Rz(0.5, q)
        
        # Random entanglement
        q1 = random.randint(0, n_qubits - 1)
        q2 = random.randint(0, n_qubits - 1)
        while q1 == q2:
            q2 = random.randint(0, n_qubits - 1)
            
        circ.CX(q1, q2)
        
    return circuit_to_qasm_str(circ)