OPENQASM 2.0;
include "qelib1.inc";
gate mcx_vchain q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { ccx q6,q12,q7; h q12; t q12; cx q5,q12; tdg q12; cx q11,q12; h q11; t q11; cx q4,q11; tdg q11; cx q10,q11; h q10; t q10; cx q3,q10; tdg q10; cx q9,q10; h q9; t q9; cx q2,q9; tdg q9; cx q8,q9; h q8; t q8; cx q0,q8; tdg q8; cx q1,q8; t q8; cx q0,q8; tdg q8; h q8; cx q8,q9; t q9; cx q2,q9; tdg q9; h q9; cx q9,q10; t q10; cx q3,q10; tdg q10; h q10; cx q10,q11; t q11; cx q4,q11; tdg q11; h q11; cx q11,q12; t q12; cx q5,q12; tdg q12; h q12; ccx q6,q12,q7; h q12; t q12; cx q5,q12; tdg q12; cx q11,q12; h q11; t q11; cx q4,q11; tdg q11; cx q10,q11; h q10; t q10; cx q3,q10; tdg q10; cx q9,q10; h q9; t q9; cx q2,q9; tdg q9; cx q8,q9; h q8; t q8; cx q0,q8; tdg q8; cx q1,q8; t q8; cx q0,q8; tdg q8; h q8; cx q8,q9; t q9; cx q2,q9; tdg q9; h q9; cx q9,q10; t q10; cx q3,q10; tdg q10; h q10; cx q10,q11; t q11; cx q4,q11; tdg q11; h q11; cx q11,q12; t q12; cx q5,q12; tdg q12; h q12; }
gate unitary q0 { u(0,-pi/8,-pi/8) q0; }
gate mcx_vchain_134450454024064 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450453955648 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate mcx_vchain_134450454023872 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450453994752 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate mcx_vchain_134450453994080 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450453964432 q0 { u(0,-pi/16,-pi/16) q0; }
gate mcx_vchain_134450454021376 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450453962992 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate mcx_vchain_134450454020176 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450453963760 q0 { u(0,-pi/16,-pi/16) q0; }
gate mcx_vchain_134450454020272 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450453961312 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate mcx_vchain_134450454003632 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450453959248 q0 { u(0,-pi/32,-pi/32) q0; }
gate mcx_vchain_134450454001184 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450453956560 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate mcx_vchain_134450453994608 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450453930368 q0 { u(0,-pi/32,-pi/32) q0; }
gate mcx_vchain_134450453989376 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450453923936 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate mcx_vchain_134450453998160 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450453958912 q0 { u(0,-pi/64,-pi/64) q0; }
gate mcx_vchain_134450453994272 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450453929456 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate mcx_vchain_134450454003152 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450453934016 q0 { u(0,-pi/64,-pi/64) q0; }
gate mcx_vchain_134450454001328 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450453933536 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate mcx_vchain_134450454001904 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450453927008 q0 { u(0,-pi/128,-pi/128) q0; }
gate mcx_vchain_134450453990624 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450454001616 q0 { u(0,-3.117048960983623,3.1661363461959633) q0; }
gate mcx_vchain_134450454002768 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450454000752 q0 { u(0,-pi/128,-pi/128) q0; }
gate mcx_vchain_134450453997872 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450454023008 q0 { u(0,-3.117048960983623,3.1661363461959633) q0; }
gate mcx_vchain_134450454000368 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450453927776 q0 { u(0,-pi/256,-pi/256) q0; }
gate mcx_vchain_134450453999984 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450453935984 q0 { u(0,-3.129320807286708,3.153864499892878) q0; }
gate mcx_vchain_134450454000080 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450454025888 q0 { u(0,-pi/256,-pi/256) q0; }
gate mcx_vchain_134450454000176 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450453922832 q0 { u(0,-3.129320807286708,3.153864499892878) q0; }
gate mcx_vchain_134450453997296 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450453925232 q0 { u(0,-pi/512,-pi/512) q0; }
gate mcx_vchain_134450454022960 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450453235136 q0 { u(0,-3.1354567304382504,3.147728576741336) q0; }
gate mcx_vchain_134450454029584 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450453236720 q0 { u(0,-pi/512,-pi/512) q0; }
gate mcx_vchain_134450454029680 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450453236672 q0 { u(0,-3.1354567304382504,3.147728576741336) q0; }
gate mcx_vchain_134450454001280 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450453246416 q0 { u(0,-pi/1024,-pi/1024) q0; }
gate mcx_vchain_134450453991200 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450453247376 q0 { u(0,-3.138524692014022,3.1446606151655643) q0; }
gate mcx_vchain_134450454003392 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450453235712 q0 { u(0,-pi/1024,-pi/1024) q0; }
gate mcx_vchain_134450454003584 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450453247616 q0 { u(0,-3.138524692014022,3.1446606151655643) q0; }
gate mcx_vchain_134450453997680 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450453240800 q0 { u(0,-pi/2048,-pi/2048) q0; }
gate unitary_134450455050432 q0 { u(0,-3.1400586728019073,3.143126634377679) q0; }
gate mcx_vchain_134450453997440 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450455044384 q0 { u(0,-pi/2048,-pi/2048) q0; }
gate unitary_134450455040976 q0 { u(0,-3.1400586728019073,3.143126634377679) q0; }
gate unitary_134450455043760 q0 { u(0,-pi/4096,-pi/4096) q0; }
gate unitary_134450453237968 q0 { u(0,-3.14082566319585,3.142359643983736) q0; }
gate unitary_134450455044912 q0 { u(0,-pi/4096,-pi/4096) q0; }
gate unitary_134450455036464 q0 { u(0,-3.14082566319585,3.142359643983736) q0; }
gate unitary_134450455052112 q0 { u(0,-pi/8192,-pi/8192) q0; }
gate unitary_134450455041984 q0 { u(0,-3.141209158392822,3.1419761487867643) q0; }
gate unitary_134450455039440 q0 { u(0,-pi/8192,-pi/8192) q0; }
gate unitary_134450454657120 q0 { u(0,-3.141209158392822,3.1419761487867643) q0; }
gate unitary_134450455042752 q0 { u(0,-0.00019174759848570517,-0.00019174759848570517) q0; }
gate unitary_134450454658512 q0 { u(0,-3.1414009059913073,3.141784401188279) q0; }
gate unitary_134450454655056 q0 { u(0,-0.00019174759848570517,-0.00019174759848570517) q0; }
gate unitary_134450454650160 q0 { u(0,-3.1414009059913073,3.141784401188279) q0; }
gate mcphase(param0) q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { mcx_vchain q0,q1,q2,q3,q4,q5,q6,q13,q7,q8,q9,q10,q11; unitary q13; mcx_vchain_134450454024064 q7,q8,q9,q10,q11,q12,q13,q3,q4,q5,q6; unitary_134450453955648 q13; mcx_vchain q0,q1,q2,q3,q4,q5,q6,q13,q7,q8,q9,q10,q11; unitary q13; mcx_vchain_134450454023872 q7,q8,q9,q10,q11,q12,q13,q3,q4,q5,q6; unitary_134450453994752 q13; mcx_vchain_134450453994080 q0,q1,q2,q3,q4,q5,q12,q6,q7,q8,q9; unitary_134450453964432 q12; mcx_vchain_134450454021376 q6,q7,q8,q9,q10,q11,q12,q2,q3,q4,q5; unitary_134450453962992 q12; mcx_vchain_134450454020176 q0,q1,q2,q3,q4,q5,q12,q6,q7,q8,q9; unitary_134450453963760 q12; mcx_vchain_134450454020272 q6,q7,q8,q9,q10,q11,q12,q2,q3,q4,q5; unitary_134450453961312 q12; mcx_vchain_134450454003632 q0,q1,q2,q3,q4,q5,q11,q6,q7,q8,q9; unitary_134450453959248 q11; mcx_vchain_134450454001184 q6,q7,q8,q9,q10,q11,q3,q4,q5; unitary_134450453956560 q11; mcx_vchain_134450453994608 q0,q1,q2,q3,q4,q5,q11,q6,q7,q8,q9; unitary_134450453930368 q11; mcx_vchain_134450453989376 q6,q7,q8,q9,q10,q11,q3,q4,q5; unitary_134450453923936 q11; mcx_vchain_134450453998160 q0,q1,q2,q3,q4,q10,q5,q6,q7; unitary_134450453958912 q10; mcx_vchain_134450453994272 q5,q6,q7,q8,q9,q10,q2,q3,q4; unitary_134450453929456 q10; mcx_vchain_134450454003152 q0,q1,q2,q3,q4,q10,q5,q6,q7; unitary_134450453934016 q10; mcx_vchain_134450454001328 q5,q6,q7,q8,q9,q10,q2,q3,q4; unitary_134450453933536 q10; mcx_vchain_134450454001904 q0,q1,q2,q3,q4,q9,q5,q6,q7; unitary_134450453927008 q9; mcx_vchain_134450453990624 q5,q6,q7,q8,q9,q3,q4; unitary_134450454001616 q9; mcx_vchain_134450454002768 q0,q1,q2,q3,q4,q9,q5,q6,q7; unitary_134450454000752 q9; mcx_vchain_134450453997872 q5,q6,q7,q8,q9,q3,q4; unitary_134450454023008 q9; mcx_vchain_134450454000368 q0,q1,q2,q3,q8,q4,q5; unitary_134450453927776 q8; mcx_vchain_134450453999984 q4,q5,q6,q7,q8,q2,q3; unitary_134450453935984 q8; mcx_vchain_134450454000080 q0,q1,q2,q3,q8,q4,q5; unitary_134450454025888 q8; mcx_vchain_134450454000176 q4,q5,q6,q7,q8,q2,q3; unitary_134450453922832 q8; mcx_vchain_134450453997296 q0,q1,q2,q3,q7,q4,q5; unitary_134450453925232 q7; mcx_vchain_134450454022960 q4,q5,q6,q7,q3; unitary_134450453235136 q7; mcx_vchain_134450454029584 q0,q1,q2,q3,q7,q4,q5; unitary_134450453236720 q7; mcx_vchain_134450454029680 q4,q5,q6,q7,q3; unitary_134450453236672 q7; mcx_vchain_134450454001280 q0,q1,q2,q6,q3; unitary_134450453246416 q6; mcx_vchain_134450453991200 q3,q4,q5,q6,q2; unitary_134450453247376 q6; mcx_vchain_134450454003392 q0,q1,q2,q6,q3; unitary_134450453235712 q6; mcx_vchain_134450454003584 q3,q4,q5,q6,q2; unitary_134450453247616 q6; mcx_vchain_134450453997680 q0,q1,q2,q5,q3; unitary_134450453240800 q5; ccx q3,q4,q5; unitary_134450455050432 q5; mcx_vchain_134450453997440 q0,q1,q2,q5,q3; unitary_134450455044384 q5; ccx q3,q4,q5; unitary_134450455040976 q5; ccx q0,q1,q4; unitary_134450455043760 q4; ccx q2,q3,q4; unitary_134450453237968 q4; ccx q0,q1,q4; unitary_134450455044912 q4; ccx q2,q3,q4; unitary_134450455036464 q4; ccx q0,q1,q3; unitary_134450455052112 q3; cx q2,q3; unitary_134450455041984 q3; ccx q0,q1,q3; unitary_134450455039440 q3; cx q2,q3; unitary_134450454657120 q3; cx q0,q2; unitary_134450455042752 q2; cx q1,q2; unitary_134450454658512 q2; cx q0,q2; unitary_134450454655056 q2; cx q1,q2; unitary_134450454650160 q2; crz(pi/4096) q0,q1; p(pi/8192) q0; }
gate mcx_vchain_134450454024880 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { rccx q0,q1,q13; rccx q2,q13,q14; rccx q3,q14,q15; rccx q4,q15,q16; rccx q5,q16,q17; rccx q6,q17,q18; rccx q7,q18,q19; rccx q8,q19,q20; rccx q9,q20,q21; rccx q10,q21,q22; ccx q11,q22,q12; rccx q10,q21,q22; rccx q9,q20,q21; rccx q8,q19,q20; rccx q7,q18,q19; rccx q6,q17,q18; rccx q5,q16,q17; rccx q4,q15,q16; rccx q3,q14,q15; rccx q2,q13,q14; rccx q0,q1,q13; }
gate gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { mcphase(pi) q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; h q12; h q11; h q10; h q9; h q8; h q7; h q6; h q5; h q4; h q3; h q2; h q1; h q0; x q0; x q1; x q2; x q3; x q4; x q5; x q6; x q7; x q8; x q9; x q10; x q11; x q12; h q12; mcx_vchain_134450454024880 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; h q12; x q0; x q1; x q2; x q3; x q4; x q5; x q6; x q7; x q8; x q9; x q10; x q11; x q12; h q0; h q1; h q2; h q3; h q4; h q5; h q6; h q7; h q8; h q9; h q10; h q11; h q12; }
gate gate_Q_134450454026944 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450453990336 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450454026800 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450454029632 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450454653232 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450454655920 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450454320368 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450454030016 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450454644880 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450454651984 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450453239264 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450454323776 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450456101760 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450456107136 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450455048272 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450455694464 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450455702048 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450455707280 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450455400368 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450455403968 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450453987456 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450455402192 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450455706656 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450457195392 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450455405312 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450457190352 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450457191840 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450456803952 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450456792384 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450456471904 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450456466672 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450456467776 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450458292736 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450456797088 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450457187664 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450458292064 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450456470896 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450458294896 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450457886688 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450457881888 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450454330448 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450457737312 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450457735488 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450457728144 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450457647520 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450457644880 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450457727856 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450457647952 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450458292160 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450455696864 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450454031504 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450457528176 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450457597936 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450457541856 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450457446688 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450457457296 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450457453168 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450454655008 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450456105024 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450457445584 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450457597264 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450457531248 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450457371104 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450457376576 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450454328144 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450457877952 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450455705456 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450459440048 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450459440336 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450457405408 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
gate gate_Q_134450459388928 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q21,q22; }
qreg q[22];
qreg flag[1];
creg meas[23];
h q[0];
h q[1];
h q[2];
h q[3];
h q[4];
h q[5];
h q[6];
h q[7];
h q[8];
h q[9];
h q[10];
h q[11];
h q[12];
x q[13];
gate_Q_134450454026944 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450453990336 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450454026800 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450454029632 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450454653232 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450454655920 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450454320368 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450454030016 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450454644880 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450454651984 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450453239264 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450454323776 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450456101760 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450456107136 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450455048272 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450455694464 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450455702048 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450455707280 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450455400368 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450455403968 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450453987456 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450455402192 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450455706656 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450457195392 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450455405312 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450457190352 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450457191840 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450456803952 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450456792384 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450456471904 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450456466672 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450456467776 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450458292736 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450456797088 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450457187664 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450458292064 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450456470896 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450458294896 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450457886688 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450457881888 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450454330448 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450457737312 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450457735488 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450457728144 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450457647520 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450457644880 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450457727856 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450457647952 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450458292160 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450455696864 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450454031504 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450457528176 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450457597936 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450457541856 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450457446688 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450457457296 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450457453168 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450454655008 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450456105024 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450457445584 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450457597264 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450457531248 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450457371104 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450457376576 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450454328144 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450457877952 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450455705456 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450459440048 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450459440336 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450457405408 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
gate_Q_134450459388928 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
barrier q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],q[15],q[16],q[17],q[18],q[19],q[20],q[21],flag[0];
measure q[0] -> meas[0];
measure q[1] -> meas[1];
measure q[2] -> meas[2];
measure q[3] -> meas[3];
measure q[4] -> meas[4];
measure q[5] -> meas[5];
measure q[6] -> meas[6];
measure q[7] -> meas[7];
measure q[8] -> meas[8];
measure q[9] -> meas[9];
measure q[10] -> meas[10];
measure q[11] -> meas[11];
measure q[12] -> meas[12];
measure q[13] -> meas[13];
measure q[14] -> meas[14];
measure q[15] -> meas[15];
measure q[16] -> meas[16];
measure q[17] -> meas[17];
measure q[18] -> meas[18];
measure q[19] -> meas[19];
measure q[20] -> meas[20];
measure q[21] -> meas[21];
measure flag[0] -> meas[22];