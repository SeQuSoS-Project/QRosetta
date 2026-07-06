OPENQASM 2.0;
include "qelib1.inc";

qreg q[3];
h q[0];
cu1(0.5*pi) q[1],q[0];
cu1(0.25*pi) q[2],q[0];
barrier q[0],q[1],q[2];
h q[1];
cu1(0.5*pi) q[2],q[1];
barrier q[0],q[1],q[2];
h q[2];
barrier q[0],q[1],q[2];
swap q[0],q[2];
