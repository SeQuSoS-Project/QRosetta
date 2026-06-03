OPENQASM 2.0;
include "qelib1.inc";
gate mcx_vchain q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary q0 { u(0,-pi/8,-pi/8) q0; }
gate unitary_134450459430784 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate unitary_134450492536832 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate unitary_134450493544768 q0 { u(0,-pi/16,-pi/16) q0; }
gate unitary_134450550277424 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate unitary_134450492556784 q0 { u(0,-pi/16,-pi/16) q0; }
gate unitary_134450610859440 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate unitary_134450454327424 q0 { u(0,-pi/32,-pi/32) q0; }
gate unitary_134450550285008 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate unitary_134450562907072 q0 { u(0,-pi/32,-pi/32) q0; }
gate unitary_134450611873472 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate unitary_134450552544848 q0 { u(0,-pi/64,-pi/64) q0; }
gate unitary_134450562902368 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate unitary_134450492740272 q0 { u(0,-pi/64,-pi/64) q0; }
gate unitary_134450493540688 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate unitary_134450552550752 q0 { u(0,-pi/128,-pi/128) q0; }
gate unitary_134450572928464 q0 { u(0,-3.117048960983623,3.1661363461959633) q0; }
gate unitary_134450611206288 q0 { u(0,-pi/128,-pi/128) q0; }
gate unitary_134450611206768 q0 { u(0,-3.117048960983623,3.1661363461959633) q0; }
gate mcphase(param0) q0,q1,q2,q3,q4,q5,q6 { mcx_vchain q0,q1,q2,q6,q3; unitary q6; mcx_vchain q3,q4,q5,q6,q2; unitary_134450459430784 q6; mcx_vchain q0,q1,q2,q6,q3; unitary q6; mcx_vchain q3,q4,q5,q6,q2; unitary_134450492536832 q6; mcx_vchain q0,q1,q2,q5,q3; unitary_134450493544768 q5; ccx q3,q4,q5; unitary_134450550277424 q5; mcx_vchain q0,q1,q2,q5,q3; unitary_134450492556784 q5; ccx q3,q4,q5; unitary_134450610859440 q5; ccx q0,q1,q4; unitary_134450454327424 q4; ccx q2,q3,q4; unitary_134450550285008 q4; ccx q0,q1,q4; unitary_134450562907072 q4; ccx q2,q3,q4; unitary_134450611873472 q4; ccx q0,q1,q3; unitary_134450552544848 q3; cx q2,q3; unitary_134450562902368 q3; ccx q0,q1,q3; unitary_134450492740272 q3; cx q2,q3; unitary_134450493540688 q3; cx q0,q2; unitary_134450552550752 q2; cx q1,q2; unitary_134450572928464 q2; cx q0,q2; unitary_134450611206288 q2; cx q1,q2; unitary_134450611206768 q2; crz(pi/32) q0,q1; p(pi/64) q0; }
gate mcx_vchain_134450549893088 q0,q1,q2,q3,q4,q5,q6,q7,q8 { rccx q0,q1,q6; rccx q2,q6,q7; rccx q3,q7,q8; ccx q4,q8,q5; rccx q3,q7,q8; rccx q2,q6,q7; rccx q0,q1,q6; }
gate gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8 { mcphase(pi) q0,q1,q2,q3,q4,q5,q6; h q5; h q4; h q3; h q2; h q1; h q0; x q0; x q1; x q2; x q3; x q4; x q5; h q5; mcx_vchain_134450549893088 q0,q1,q2,q3,q4,q5,q6,q7,q8; h q5; x q0; x q1; x q2; x q3; x q4; x q5; h q0; h q1; h q2; h q3; h q4; h q5; }
gate gate_Q_134450549883248 q0,q1,q2,q3,q4,q5,q6,q7,q8 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8; }
gate gate_Q_134450492780432 q0,q1,q2,q3,q4,q5,q6,q7,q8 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8; }
gate gate_Q_134450572931728 q0,q1,q2,q3,q4,q5,q6,q7,q8 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8; }
gate gate_Q_134450455704160 q0,q1,q2,q3,q4,q5,q6,q7,q8 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8; }
gate gate_Q_134450488295792 q0,q1,q2,q3,q4,q5,q6,q7,q8 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8; }
gate gate_Q_134450492603856 q0,q1,q2,q3,q4,q5,q6,q7,q8 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8; }
qreg q[8];
qreg flag[1];
creg meas[9];
h q[0];
h q[1];
h q[2];
h q[3];
h q[4];
h q[5];
x q[6];
gate_Q_134450549883248 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],flag[0];
gate_Q_134450492780432 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],flag[0];
gate_Q_134450572931728 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],flag[0];
gate_Q_134450455704160 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],flag[0];
gate_Q_134450488295792 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],flag[0];
gate_Q_134450492603856 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],flag[0];
barrier q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],flag[0];
measure q[0] -> meas[0];
measure q[1] -> meas[1];
measure q[2] -> meas[2];
measure q[3] -> meas[3];
measure q[4] -> meas[4];
measure q[5] -> meas[5];
measure q[6] -> meas[6];
measure q[7] -> meas[7];
measure flag[0] -> meas[8];