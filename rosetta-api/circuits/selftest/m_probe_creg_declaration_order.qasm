OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg b[1];
creg a[1];
x q[0];
measure q[0] -> b[0];
measure q[1] -> a[0];
