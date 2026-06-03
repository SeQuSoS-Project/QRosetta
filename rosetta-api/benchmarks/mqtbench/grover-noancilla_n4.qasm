OPENQASM 2.0;
include "qelib1.inc";
gate unitary q0 { u(0,-pi/8,-pi/8) q0; }
gate unitary_134450611531760 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate unitary_134450611526624 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate unitary_134450611520192 q0 { u(0,-pi/16,-pi/16) q0; }
gate unitary_134450611519808 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate unitary_134450611523888 q0 { u(0,-pi/16,-pi/16) q0; }
gate unitary_134450611534928 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate mcphase(param0) q0,q1,q2,q3 { ccx q0,q1,q3; unitary q3; cx q2,q3; unitary_134450611531760 q3; ccx q0,q1,q3; unitary q3; cx q2,q3; unitary_134450611526624 q3; cx q0,q2; unitary_134450611520192 q2; cx q1,q2; unitary_134450611519808 q2; cx q0,q2; unitary_134450611523888 q2; cx q1,q2; unitary_134450611534928 q2; crz(pi/4) q0,q1; p(pi/8) q0; }
gate gate_Q q0,q1,q2,q3 { mcphase(pi) q0,q1,q2,q3; h q2; h q1; h q0; x q0; x q1; x q2; h q2; ccx q0,q1,q2; h q2; x q0; x q1; x q2; h q0; h q1; h q2; }
gate gate_Q_134450612675568 q0,q1,q2,q3 { gate_Q q0,q1,q2,q3; }
gate gate_Q_134450611520768 q0,q1,q2,q3 { gate_Q q0,q1,q2,q3; }
qreg q[3];
qreg flag[1];
creg meas[4];
h q[0];
h q[1];
h q[2];
x flag[0];
gate_Q_134450612675568 q[0],q[1],q[2],flag[0];
gate_Q_134450611520768 q[0],q[1],q[2],flag[0];
barrier q[0],q[1],q[2],flag[0];
measure q[0] -> meas[0];
measure q[1] -> meas[1];
measure q[2] -> meas[2];
measure flag[0] -> meas[3];