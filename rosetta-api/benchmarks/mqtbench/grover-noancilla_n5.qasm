OPENQASM 2.0;
include "qelib1.inc";
gate unitary q0 { u(0,-pi/8,-pi/8) q0; }
gate unitary_134450613324016 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate unitary_134450610375280 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate unitary_134450613324448 q0 { u(0,-pi/16,-pi/16) q0; }
gate unitary_134450612836000 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate unitary_134450612340016 q0 { u(0,-pi/16,-pi/16) q0; }
gate unitary_134450612341312 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate unitary_134450612345008 q0 { u(0,-pi/32,-pi/32) q0; }
gate unitary_134450612350576 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate unitary_134450612345440 q0 { u(0,-pi/32,-pi/32) q0; }
gate unitary_134450611525808 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate mcphase(param0) q0,q1,q2,q3,q4 { ccx q0,q1,q4; unitary q4; ccx q2,q3,q4; unitary_134450613324016 q4; ccx q0,q1,q4; unitary q4; ccx q2,q3,q4; unitary_134450610375280 q4; ccx q0,q1,q3; unitary_134450613324448 q3; cx q2,q3; unitary_134450612836000 q3; ccx q0,q1,q3; unitary_134450612340016 q3; cx q2,q3; unitary_134450612341312 q3; cx q0,q2; unitary_134450612345008 q2; cx q1,q2; unitary_134450612350576 q2; cx q0,q2; unitary_134450612345440 q2; cx q1,q2; unitary_134450611525808 q2; crz(pi/8) q0,q1; p(pi/16) q0; }
gate mcx q0,q1,q2,q3 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate gate_Q q0,q1,q2,q3,q4 { mcphase(pi) q0,q1,q2,q3,q4; h q3; h q2; h q1; h q0; x q0; x q1; x q2; x q3; h q3; mcx q0,q1,q2,q3; h q3; x q0; x q1; x q2; x q3; h q0; h q1; h q2; h q3; }
gate gate_Q_134450612675952 q0,q1,q2,q3,q4 { gate_Q q0,q1,q2,q3,q4; }
gate gate_Q_134450612674848 q0,q1,q2,q3,q4 { gate_Q q0,q1,q2,q3,q4; }
gate gate_Q_134450612341408 q0,q1,q2,q3,q4 { gate_Q q0,q1,q2,q3,q4; }
qreg q[4];
qreg flag[1];
creg meas[5];
h q[0];
h q[1];
h q[2];
h q[3];
x flag[0];
gate_Q_134450612675952 q[0],q[1],q[2],q[3],flag[0];
gate_Q_134450612674848 q[0],q[1],q[2],q[3],flag[0];
gate_Q_134450612341408 q[0],q[1],q[2],q[3],flag[0];
barrier q[0],q[1],q[2],q[3],flag[0];
measure q[0] -> meas[0];
measure q[1] -> meas[1];
measure q[2] -> meas[2];
measure q[3] -> meas[3];
measure flag[0] -> meas[4];