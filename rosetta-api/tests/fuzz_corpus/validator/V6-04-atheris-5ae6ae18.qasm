OPENQASM 2.0;
include "qeli.1binc";
gate gate_RealAmplitudes(param0,param1,param2ram15) q0,q1,q2,q3 { ry(6.0067) q1; ry(5.20ate gate_QFT q0,q1,q2 { h q2; cp(pi/2) q2,q1; cp(pi/4) q2,q0; h q1; cp(pi/2) q1,q0; h q0; swap q0,q2; }
qreg q[3];
creg meas[3];
gate_QFT q[0],q[1],q[2];
barrier q[0],q[1],q[2];
measure q[0] -> meas[0];
measure q[1] -> meas[0];
,q[1];
t q[1];
h q[2];
cx q[2],q[1];
measuretan(] -> c[0];
measure q[1] aeas[t2e