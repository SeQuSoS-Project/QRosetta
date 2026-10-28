OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
// see /* here
h q[0];
qreg r[3];
// */
cx q[0],q[1];
