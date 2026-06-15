OPENQASM 2.0;
include "qelib1.inc";
gate unitary q0 { u(0,-pi/8,-pi/8) q0; }
gate unitary_134450456473104 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate unitary_134450458289424 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate unitary_134450457198416 q0 { u(0,-pi/16,-pi/16) q0; }
gate unitary_134450455410496 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate unitary_134450458292208 q0 { u(0,-pi/16,-pi/16) q0; }
gate unitary_134450457874256 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate mcphase(param0) q0,q1,q2,q3 { ccx q0,q1,q3; unitary q3; cx q2,q3; unitary_134450456473104 q3; ccx q0,q1,q3; unitary q3; cx q2,q3; unitary_134450458289424 q3; cx q0,q2; unitary_134450457198416 q2; cx q1,q2; unitary_134450455410496 q2; cx q0,q2; unitary_134450458292208 q2; cx q1,q2; unitary_134450457874256 q2; crz(pi/4) q0,q1; p(pi/8) q0; }
gate gate_Q q0,q1,q2,q3 { mcphase(pi) q0,q1,q2,q3; h q2; h q1; h q0; x q0; x q1; x q2; h q2; ccx q0,q1,q2; h q2; x q0; x q1; x q2; h q0; h q1; h q2; }
gate gate_Q_134450454655008 q0,q1,q2,q3 { gate_Q q0,q1,q2,q3; }
gate gate_Q_134450456802944 q0,q1,q2,q3 { gate_Q q0,q1,q2,q3; }
qreg q[3];
qreg flag[1];
creg meas[4];
h q[0];
h q[1];
h q[2];
x flag[0];
gate_Q_134450454655008 q[0],q[1],q[2],flag[0];
gate_Q_134450456802944 q[0],q[1],q[2],flag[0];
barrier q[0],q[1],q[2],flag[0];
measure q[0] -> meas[0];
measure q[1] -> meas[1];
measure q[2] -> meas[2];
measure flag[0] -> meas[3];