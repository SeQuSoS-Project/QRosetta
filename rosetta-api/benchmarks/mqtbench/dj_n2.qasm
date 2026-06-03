OPENQASM 2.0;
include "qelib1.inc";
gate gate_Oracle q0,q1 { x q0; cx q0,q1; x q0; }
qreg q[2];
creg c[1];
x q[1];
h q[1];
h q[0];
gate_Oracle q[0],q[1];
h q[0];
barrier q[0],q[1];
measure q[0] -> c[0];