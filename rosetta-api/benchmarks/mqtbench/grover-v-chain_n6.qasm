OPENQASM 2.0;
include "qelib1.inc";
gate mcx_vchain q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary q0 { u(0,-pi/8,-pi/8) q0; }
gate unitary_134450452171808 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate unitary_134450458999312 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate unitary_134450458998256 q0 { u(0,-pi/16,-pi/16) q0; }
gate unitary_134450458986304 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate unitary_134450459311904 q0 { u(0,-pi/16,-pi/16) q0; }
gate unitary_134450453998064 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate unitary_134450458936576 q0 { u(0,-pi/32,-pi/32) q0; }
gate unitary_134450458899328 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate unitary_134450458888720 q0 { u(0,-pi/32,-pi/32) q0; }
gate unitary_134450458853648 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate unitary_134450458855568 q0 { u(0,-pi/64,-pi/64) q0; }
gate unitary_134450458895776 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate unitary_134450454125056 q0 { u(0,-pi/64,-pi/64) q0; }
gate unitary_134450458855856 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate mcphase(param0) q0,q1,q2,q3,q4,q5 { mcx_vchain q0,q1,q2,q5,q3; unitary q5; ccx q3,q4,q5; unitary_134450452171808 q5; mcx_vchain q0,q1,q2,q5,q3; unitary q5; ccx q3,q4,q5; unitary_134450458999312 q5; ccx q0,q1,q4; unitary_134450458998256 q4; ccx q2,q3,q4; unitary_134450458986304 q4; ccx q0,q1,q4; unitary_134450459311904 q4; ccx q2,q3,q4; unitary_134450453998064 q4; ccx q0,q1,q3; unitary_134450458936576 q3; cx q2,q3; unitary_134450458899328 q3; ccx q0,q1,q3; unitary_134450458888720 q3; cx q2,q3; unitary_134450458853648 q3; cx q0,q2; unitary_134450458855568 q2; cx q1,q2; unitary_134450458895776 q2; cx q0,q2; unitary_134450454125056 q2; cx q1,q2; unitary_134450458855856 q2; crz(pi/16) q0,q1; p(pi/32) q0; }
gate mcx_vchain_134450454655728 q0,q1,q2,q3,q4,q5,q6 { rccx q0,q1,q5; rccx q2,q5,q6; ccx q3,q6,q4; rccx q2,q5,q6; rccx q0,q1,q5; }
gate gate_Q q0,q1,q2,q3,q4,q5,q6 { mcphase(pi) q0,q1,q2,q3,q4,q5; h q4; h q3; h q2; h q1; h q0; x q0; x q1; x q2; x q3; x q4; h q4; mcx_vchain_134450454655728 q0,q1,q2,q3,q4,q5,q6; h q4; x q0; x q1; x q2; x q3; x q4; h q0; h q1; h q2; h q3; h q4; }
gate gate_Q_134450455043808 q0,q1,q2,q3,q4,q5,q6 { gate_Q q0,q1,q2,q3,q4,q5,q6; }
gate gate_Q_134450455700320 q0,q1,q2,q3,q4,q5,q6 { gate_Q q0,q1,q2,q3,q4,q5,q6; }
gate gate_Q_134450454329824 q0,q1,q2,q3,q4,q5,q6 { gate_Q q0,q1,q2,q3,q4,q5,q6; }
gate gate_Q_134450459043328 q0,q1,q2,q3,q4,q5,q6 { gate_Q q0,q1,q2,q3,q4,q5,q6; }
qreg q[6];
qreg flag[1];
creg meas[7];
h q[0];
h q[1];
h q[2];
h q[3];
h q[4];
x q[5];
gate_Q_134450455043808 q[0],q[1],q[2],q[3],q[4],q[5],flag[0];
gate_Q_134450455700320 q[0],q[1],q[2],q[3],q[4],q[5],flag[0];
gate_Q_134450454329824 q[0],q[1],q[2],q[3],q[4],q[5],flag[0];
gate_Q_134450459043328 q[0],q[1],q[2],q[3],q[4],q[5],flag[0];
barrier q[0],q[1],q[2],q[3],q[4],q[5],flag[0];
measure q[0] -> meas[0];
measure q[1] -> meas[1];
measure q[2] -> meas[2];
measure q[3] -> meas[3];
measure q[4] -> meas[4];
measure q[5] -> meas[5];
measure flag[0] -> meas[6];