OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg a[2];
creg b[1];
x q[1];
measure q[0] -> a[0];
measure q[1] -> b[0];
