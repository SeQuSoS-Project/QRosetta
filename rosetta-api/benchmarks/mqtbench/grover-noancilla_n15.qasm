OPENQASM 2.0;
include "qelib1.inc";
gate mcx_vchain q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { ccx q6,q12,q7; h q12; t q12; cx q5,q12; tdg q12; cx q11,q12; h q11; t q11; cx q4,q11; tdg q11; cx q10,q11; h q10; t q10; cx q3,q10; tdg q10; cx q9,q10; h q9; t q9; cx q2,q9; tdg q9; cx q8,q9; h q8; t q8; cx q0,q8; tdg q8; cx q1,q8; t q8; cx q0,q8; tdg q8; h q8; cx q8,q9; t q9; cx q2,q9; tdg q9; h q9; cx q9,q10; t q10; cx q3,q10; tdg q10; h q10; cx q10,q11; t q11; cx q4,q11; tdg q11; h q11; cx q11,q12; t q12; cx q5,q12; tdg q12; h q12; ccx q6,q12,q7; h q12; t q12; cx q5,q12; tdg q12; cx q11,q12; h q11; t q11; cx q4,q11; tdg q11; cx q10,q11; h q10; t q10; cx q3,q10; tdg q10; cx q9,q10; h q9; t q9; cx q2,q9; tdg q9; cx q8,q9; h q8; t q8; cx q0,q8; tdg q8; cx q1,q8; t q8; cx q0,q8; tdg q8; h q8; cx q8,q9; t q9; cx q2,q9; tdg q9; h q9; cx q9,q10; t q10; cx q3,q10; tdg q10; h q10; cx q10,q11; t q11; cx q4,q11; tdg q11; h q11; cx q11,q12; t q12; cx q5,q12; tdg q12; h q12; }
gate unitary q0 { u(0,-pi/8,-pi/8) q0; }
gate unitary_134450573057712 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate unitary_134450573291264 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate unitary_134450567683136 q0 { u(0,-pi/16,-pi/16) q0; }
gate mcx_vchain_134450571792256 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450573062704 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate unitary_134450572920976 q0 { u(0,-pi/16,-pi/16) q0; }
gate mcx_vchain_134450571788704 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450572926976 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate mcx_vchain_134450571792064 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450572932112 q0 { u(0,-pi/32,-pi/32) q0; }
gate mcx_vchain_134450571794896 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450572934320 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate mcx_vchain_134450571794128 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450572769040 q0 { u(0,-pi/32,-pi/32) q0; }
gate mcx_vchain_134450571793360 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450572767648 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate mcx_vchain_134450573291504 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450572924144 q0 { u(0,-pi/64,-pi/64) q0; }
gate mcx_vchain_134450573294576 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450572761984 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate mcx_vchain_134450573294768 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450574708176 q0 { u(0,-pi/64,-pi/64) q0; }
gate mcx_vchain_134450573294048 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450574713408 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate mcx_vchain_134450573282192 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450574712592 q0 { u(0,-pi/128,-pi/128) q0; }
gate mcx_vchain_134450573291120 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450566417872 q0 { u(0,-3.117048960983623,3.1661363461959633) q0; }
gate mcx_vchain_134450573293376 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450574710768 q0 { u(0,-pi/128,-pi/128) q0; }
gate mcx_vchain_134450573287664 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450574709376 q0 { u(0,-3.117048960983623,3.1661363461959633) q0; }
gate mcx_vchain_134450573293040 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450574712832 q0 { u(0,-pi/256,-pi/256) q0; }
gate mcx_vchain_134450573295056 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450574322016 q0 { u(0,-3.129320807286708,3.153864499892878) q0; }
gate mcx_vchain_134450573283296 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450574706352 q0 { u(0,-pi/256,-pi/256) q0; }
gate mcx_vchain_134450573285408 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450574313856 q0 { u(0,-3.129320807286708,3.153864499892878) q0; }
gate mcx_vchain_134450573283344 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450574316928 q0 { u(0,-pi/512,-pi/512) q0; }
gate mcx_vchain_134450573284304 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450574327536 q0 { u(0,-3.1354567304382504,3.147728576741336) q0; }
gate mcx_vchain_134450573284400 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450574315728 q0 { u(0,-pi/512,-pi/512) q0; }
gate mcx_vchain_134450573284496 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450574717536 q0 { u(0,-3.1354567304382504,3.147728576741336) q0; }
gate mcx_vchain_134450573285216 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450574326096 q0 { u(0,-pi/1024,-pi/1024) q0; }
gate mcx_vchain_134450573292656 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450574048288 q0 { u(0,-3.138524692014022,3.1446606151655643) q0; }
gate mcx_vchain_134450573281232 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450574044208 q0 { u(0,-pi/1024,-pi/1024) q0; }
gate mcx_vchain_134450573295248 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450574037344 q0 { u(0,-3.138524692014022,3.1446606151655643) q0; }
gate mcx_vchain_134450571803680 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450571804064 q0 { u(0,-pi/2048,-pi/2048) q0; }
gate mcx_vchain_134450571789280 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450574042864 q0 { u(0,-3.1400586728019073,3.143126634377679) q0; }
gate mcx_vchain_134450571788464 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450574036096 q0 { u(0,-pi/2048,-pi/2048) q0; }
gate mcx_vchain_134450571798352 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450573823824 q0 { u(0,-3.1400586728019073,3.143126634377679) q0; }
gate mcx_vchain_134450573283152 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450574033552 q0 { u(0,-pi/4096,-pi/4096) q0; }
gate unitary_134450574715280 q0 { u(0,-3.14082566319585,3.142359643983736) q0; }
gate mcx_vchain_134450573286656 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450573829824 q0 { u(0,-pi/4096,-pi/4096) q0; }
gate unitary_134450573823728 q0 { u(0,-3.14082566319585,3.142359643983736) q0; }
gate unitary_134450610152432 q0 { u(0,-pi/8192,-pi/8192) q0; }
gate unitary_134450610152720 q0 { u(0,-3.141209158392822,3.1419761487867643) q0; }
gate unitary_134450610153968 q0 { u(0,-pi/8192,-pi/8192) q0; }
gate unitary_134450574037056 q0 { u(0,-3.141209158392822,3.1419761487867643) q0; }
gate unitary_134450610153344 q0 { u(0,-0.00019174759848570517,-0.00019174759848570517) q0; }
gate unitary_134450610145280 q0 { u(0,-3.1414009059913073,3.141784401188279) q0; }
gate unitary_134450610645008 q0 { u(0,-0.00019174759848570517,-0.00019174759848570517) q0; }
gate unitary_134450610646112 q0 { u(0,-3.1414009059913073,3.141784401188279) q0; }
gate unitary_134450610640688 q0 { u(0,-pi/32768,-pi/32768) q0; }
gate unitary_134450610641216 q0 { u(0,-3.1414967797905504,3.141688527389036) q0; }
gate unitary_134450573824928 q0 { u(0,-pi/32768,-pi/32768) q0; }
gate unitary_134450574049056 q0 { u(0,-3.1414967797905504,3.141688527389036) q0; }
gate mcphase(param0) q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { mcx_vchain q0,q1,q2,q3,q4,q5,q6,q14,q7,q8,q9,q10,q11; unitary q14; mcx_vchain q7,q8,q9,q10,q11,q12,q13,q14,q2,q3,q4,q5,q6; unitary_134450573057712 q14; mcx_vchain q0,q1,q2,q3,q4,q5,q6,q14,q7,q8,q9,q10,q11; unitary q14; mcx_vchain q7,q8,q9,q10,q11,q12,q13,q14,q2,q3,q4,q5,q6; unitary_134450573291264 q14; mcx_vchain q0,q1,q2,q3,q4,q5,q6,q13,q7,q8,q9,q10,q11; unitary_134450567683136 q13; mcx_vchain_134450571792256 q7,q8,q9,q10,q11,q12,q13,q3,q4,q5,q6; unitary_134450573062704 q13; mcx_vchain q0,q1,q2,q3,q4,q5,q6,q13,q7,q8,q9,q10,q11; unitary_134450572920976 q13; mcx_vchain_134450571788704 q7,q8,q9,q10,q11,q12,q13,q3,q4,q5,q6; unitary_134450572926976 q13; mcx_vchain_134450571792064 q0,q1,q2,q3,q4,q5,q12,q6,q7,q8,q9; unitary_134450572932112 q12; mcx_vchain_134450571794896 q6,q7,q8,q9,q10,q11,q12,q2,q3,q4,q5; unitary_134450572934320 q12; mcx_vchain_134450571794128 q0,q1,q2,q3,q4,q5,q12,q6,q7,q8,q9; unitary_134450572769040 q12; mcx_vchain_134450571793360 q6,q7,q8,q9,q10,q11,q12,q2,q3,q4,q5; unitary_134450572767648 q12; mcx_vchain_134450573291504 q0,q1,q2,q3,q4,q5,q11,q6,q7,q8,q9; unitary_134450572924144 q11; mcx_vchain_134450573294576 q6,q7,q8,q9,q10,q11,q3,q4,q5; unitary_134450572761984 q11; mcx_vchain_134450573294768 q0,q1,q2,q3,q4,q5,q11,q6,q7,q8,q9; unitary_134450574708176 q11; mcx_vchain_134450573294048 q6,q7,q8,q9,q10,q11,q3,q4,q5; unitary_134450574713408 q11; mcx_vchain_134450573282192 q0,q1,q2,q3,q4,q10,q5,q6,q7; unitary_134450574712592 q10; mcx_vchain_134450573291120 q5,q6,q7,q8,q9,q10,q2,q3,q4; unitary_134450566417872 q10; mcx_vchain_134450573293376 q0,q1,q2,q3,q4,q10,q5,q6,q7; unitary_134450574710768 q10; mcx_vchain_134450573287664 q5,q6,q7,q8,q9,q10,q2,q3,q4; unitary_134450574709376 q10; mcx_vchain_134450573293040 q0,q1,q2,q3,q4,q9,q5,q6,q7; unitary_134450574712832 q9; mcx_vchain_134450573295056 q5,q6,q7,q8,q9,q3,q4; unitary_134450574322016 q9; mcx_vchain_134450573283296 q0,q1,q2,q3,q4,q9,q5,q6,q7; unitary_134450574706352 q9; mcx_vchain_134450573285408 q5,q6,q7,q8,q9,q3,q4; unitary_134450574313856 q9; mcx_vchain_134450573283344 q0,q1,q2,q3,q8,q4,q5; unitary_134450574316928 q8; mcx_vchain_134450573284304 q4,q5,q6,q7,q8,q2,q3; unitary_134450574327536 q8; mcx_vchain_134450573284400 q0,q1,q2,q3,q8,q4,q5; unitary_134450574315728 q8; mcx_vchain_134450573284496 q4,q5,q6,q7,q8,q2,q3; unitary_134450574717536 q8; mcx_vchain_134450573285216 q0,q1,q2,q3,q7,q4,q5; unitary_134450574326096 q7; mcx_vchain_134450573292656 q4,q5,q6,q7,q3; unitary_134450574048288 q7; mcx_vchain_134450573281232 q0,q1,q2,q3,q7,q4,q5; unitary_134450574044208 q7; mcx_vchain_134450573295248 q4,q5,q6,q7,q3; unitary_134450574037344 q7; mcx_vchain_134450571803680 q0,q1,q2,q6,q3; unitary_134450571804064 q6; mcx_vchain_134450571789280 q3,q4,q5,q6,q2; unitary_134450574042864 q6; mcx_vchain_134450571788464 q0,q1,q2,q6,q3; unitary_134450574036096 q6; mcx_vchain_134450571798352 q3,q4,q5,q6,q2; unitary_134450573823824 q6; mcx_vchain_134450573283152 q0,q1,q2,q5,q3; unitary_134450574033552 q5; ccx q3,q4,q5; unitary_134450574715280 q5; mcx_vchain_134450573286656 q0,q1,q2,q5,q3; unitary_134450573829824 q5; ccx q3,q4,q5; unitary_134450573823728 q5; ccx q0,q1,q4; unitary_134450610152432 q4; ccx q2,q3,q4; unitary_134450610152720 q4; ccx q0,q1,q4; unitary_134450610153968 q4; ccx q2,q3,q4; unitary_134450574037056 q4; ccx q0,q1,q3; unitary_134450610153344 q3; cx q2,q3; unitary_134450610145280 q3; ccx q0,q1,q3; unitary_134450610645008 q3; cx q2,q3; unitary_134450610646112 q3; cx q0,q2; unitary_134450610640688 q2; cx q1,q2; unitary_134450610641216 q2; cx q0,q2; unitary_134450573824928 q2; cx q1,q2; unitary_134450574049056 q2; crz(pi/8192) q0,q1; p(pi/16384) q0; }
gate mcx_vchain_134450571800656 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450610990992 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate mcx_vchain_134450571802192 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450610729424 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate mcx_vchain_134450610642944 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450610512208 q0 { u(0,-pi/16,-pi/16) q0; }
gate mcx_vchain_134450610651056 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450610504432 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate mcx_vchain_134450610648464 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450573293136 q0 { u(0,-pi/16,-pi/16) q0; }
gate mcx_vchain_134450610647360 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450610557376 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate mcx_vchain_134450610981536 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450610556416 q0 { u(0,-pi/32,-pi/32) q0; }
gate mcx_vchain_134450610981296 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450610565152 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate mcx_vchain_134450610991904 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450610562032 q0 { u(0,-pi/32,-pi/32) q0; }
gate mcx_vchain_134450610982112 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450610565824 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate mcx_vchain_134450610640880 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450613717616 q0 { u(0,-pi/64,-pi/64) q0; }
gate mcx_vchain_134450610648512 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450613726688 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate mcx_vchain_134450573616592 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450613718432 q0 { u(0,-pi/64,-pi/64) q0; }
gate mcx_vchain_134450610648896 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450611877456 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate mcx_vchain_134450610992336 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450611864256 q0 { u(0,-pi/128,-pi/128) q0; }
gate mcx_vchain_134450610980960 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450611872080 q0 { u(0,-3.117048960983623,3.1661363461959633) q0; }
gate mcx_vchain_134450610989408 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450611877312 q0 { u(0,-pi/128,-pi/128) q0; }
gate mcx_vchain_134450610989120 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450611865888 q0 { u(0,-3.117048960983623,3.1661363461959633) q0; }
gate mcx_vchain_134450610727216 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450611874240 q0 { u(0,-pi/256,-pi/256) q0; }
gate mcx_vchain_134450610723328 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450611879328 q0 { u(0,-3.129320807286708,3.153864499892878) q0; }
gate mcx_vchain_134450610718624 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450611875296 q0 { u(0,-pi/256,-pi/256) q0; }
gate mcx_vchain_134450610718192 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450611868480 q0 { u(0,-3.129320807286708,3.153864499892878) q0; }
gate mcx_vchain_134450610726640 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450611873856 q0 { u(0,-pi/512,-pi/512) q0; }
gate mcx_vchain_134450610721792 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450613186208 q0 { u(0,-3.1354567304382504,3.147728576741336) q0; }
gate mcx_vchain_134450610731248 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450611870016 q0 { u(0,-pi/512,-pi/512) q0; }
gate mcx_vchain_134450610724144 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450613190624 q0 { u(0,-3.1354567304382504,3.147728576741336) q0; }
gate mcx_vchain_134450610730960 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450613187600 q0 { u(0,-pi/1024,-pi/1024) q0; }
gate mcx_vchain_134450610719392 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450613181552 q0 { u(0,-3.138524692014022,3.1446606151655643) q0; }
gate mcx_vchain_134450610732496 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450567975168 q0 { u(0,-pi/1024,-pi/1024) q0; }
gate mcx_vchain_134450610732160 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450613175936 q0 { u(0,-3.138524692014022,3.1446606151655643) q0; }
gate mcx_vchain_134450612730480 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450613176944 q0 { u(0,-pi/2048,-pi/2048) q0; }
gate unitary_134450613180304 q0 { u(0,-3.1400586728019073,3.143126634377679) q0; }
gate mcx_vchain_134450612726112 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450611206624 q0 { u(0,-pi/2048,-pi/2048) q0; }
gate unitary_134450615422464 q0 { u(0,-3.1400586728019073,3.143126634377679) q0; }
gate unitary_134450613187168 q0 { u(0,-pi/4096,-pi/4096) q0; }
gate unitary_134450611192080 q0 { u(0,-3.14082566319585,3.142359643983736) q0; }
gate unitary_134450611197024 q0 { u(0,-pi/4096,-pi/4096) q0; }
gate unitary_134450611205472 q0 { u(0,-3.14082566319585,3.142359643983736) q0; }
gate unitary_134450611203264 q0 { u(0,-pi/8192,-pi/8192) q0; }
gate unitary_134450611197072 q0 { u(0,-3.141209158392822,3.1419761487867643) q0; }
gate unitary_134450611875584 q0 { u(0,-pi/8192,-pi/8192) q0; }
gate unitary_134450611200432 q0 { u(0,-3.141209158392822,3.1419761487867643) q0; }
gate unitary_134450611195680 q0 { u(0,-0.00019174759848570517,-0.00019174759848570517) q0; }
gate unitary_134450612321504 q0 { u(0,-3.1414009059913073,3.141784401188279) q0; }
gate unitary_134450612312096 q0 { u(0,-0.00019174759848570517,-0.00019174759848570517) q0; }
gate unitary_134450612312240 q0 { u(0,-3.1414009059913073,3.141784401188279) q0; }
gate mcphase_134450573293616(param0) q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { mcx_vchain q0,q1,q2,q3,q4,q5,q6,q13,q7,q8,q9,q10,q11; unitary q13; mcx_vchain_134450571800656 q7,q8,q9,q10,q11,q12,q13,q3,q4,q5,q6; unitary_134450610990992 q13; mcx_vchain q0,q1,q2,q3,q4,q5,q6,q13,q7,q8,q9,q10,q11; unitary q13; mcx_vchain_134450571802192 q7,q8,q9,q10,q11,q12,q13,q3,q4,q5,q6; unitary_134450610729424 q13; mcx_vchain_134450610642944 q0,q1,q2,q3,q4,q5,q12,q6,q7,q8,q9; unitary_134450610512208 q12; mcx_vchain_134450610651056 q6,q7,q8,q9,q10,q11,q12,q2,q3,q4,q5; unitary_134450610504432 q12; mcx_vchain_134450610648464 q0,q1,q2,q3,q4,q5,q12,q6,q7,q8,q9; unitary_134450573293136 q12; mcx_vchain_134450610647360 q6,q7,q8,q9,q10,q11,q12,q2,q3,q4,q5; unitary_134450610557376 q12; mcx_vchain_134450610981536 q0,q1,q2,q3,q4,q5,q11,q6,q7,q8,q9; unitary_134450610556416 q11; mcx_vchain_134450610981296 q6,q7,q8,q9,q10,q11,q3,q4,q5; unitary_134450610565152 q11; mcx_vchain_134450610991904 q0,q1,q2,q3,q4,q5,q11,q6,q7,q8,q9; unitary_134450610562032 q11; mcx_vchain_134450610982112 q6,q7,q8,q9,q10,q11,q3,q4,q5; unitary_134450610565824 q11; mcx_vchain_134450610640880 q0,q1,q2,q3,q4,q10,q5,q6,q7; unitary_134450613717616 q10; mcx_vchain_134450610648512 q5,q6,q7,q8,q9,q10,q2,q3,q4; unitary_134450613726688 q10; mcx_vchain_134450573616592 q0,q1,q2,q3,q4,q10,q5,q6,q7; unitary_134450613718432 q10; mcx_vchain_134450610648896 q5,q6,q7,q8,q9,q10,q2,q3,q4; unitary_134450611877456 q10; mcx_vchain_134450610992336 q0,q1,q2,q3,q4,q9,q5,q6,q7; unitary_134450611864256 q9; mcx_vchain_134450610980960 q5,q6,q7,q8,q9,q3,q4; unitary_134450611872080 q9; mcx_vchain_134450610989408 q0,q1,q2,q3,q4,q9,q5,q6,q7; unitary_134450611877312 q9; mcx_vchain_134450610989120 q5,q6,q7,q8,q9,q3,q4; unitary_134450611865888 q9; mcx_vchain_134450610727216 q0,q1,q2,q3,q8,q4,q5; unitary_134450611874240 q8; mcx_vchain_134450610723328 q4,q5,q6,q7,q8,q2,q3; unitary_134450611879328 q8; mcx_vchain_134450610718624 q0,q1,q2,q3,q8,q4,q5; unitary_134450611875296 q8; mcx_vchain_134450610718192 q4,q5,q6,q7,q8,q2,q3; unitary_134450611868480 q8; mcx_vchain_134450610726640 q0,q1,q2,q3,q7,q4,q5; unitary_134450611873856 q7; mcx_vchain_134450610721792 q4,q5,q6,q7,q3; unitary_134450613186208 q7; mcx_vchain_134450610731248 q0,q1,q2,q3,q7,q4,q5; unitary_134450611870016 q7; mcx_vchain_134450610724144 q4,q5,q6,q7,q3; unitary_134450613190624 q7; mcx_vchain_134450610730960 q0,q1,q2,q6,q3; unitary_134450613187600 q6; mcx_vchain_134450610719392 q3,q4,q5,q6,q2; unitary_134450613181552 q6; mcx_vchain_134450610732496 q0,q1,q2,q6,q3; unitary_134450567975168 q6; mcx_vchain_134450610732160 q3,q4,q5,q6,q2; unitary_134450613175936 q6; mcx_vchain_134450612730480 q0,q1,q2,q5,q3; unitary_134450613176944 q5; ccx q3,q4,q5; unitary_134450613180304 q5; mcx_vchain_134450612726112 q0,q1,q2,q5,q3; unitary_134450611206624 q5; ccx q3,q4,q5; unitary_134450615422464 q5; ccx q0,q1,q4; unitary_134450613187168 q4; ccx q2,q3,q4; unitary_134450611192080 q4; ccx q0,q1,q4; unitary_134450611197024 q4; ccx q2,q3,q4; unitary_134450611205472 q4; ccx q0,q1,q3; unitary_134450611203264 q3; cx q2,q3; unitary_134450611197072 q3; ccx q0,q1,q3; unitary_134450611875584 q3; cx q2,q3; unitary_134450611200432 q3; cx q0,q2; unitary_134450611195680 q2; cx q1,q2; unitary_134450612321504 q2; cx q0,q2; unitary_134450612312096 q2; cx q1,q2; unitary_134450612312240 q2; crz(pi/4096) q0,q1; p(pi/8192) q0; }
gate mcx q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { h q13; mcphase_134450573293616(pi) q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; h q13; }
gate gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { mcphase(pi) q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; h q13; h q12; h q11; h q10; h q9; h q8; h q7; h q6; h q5; h q4; h q3; h q2; h q1; h q0; x q0; x q1; x q2; x q3; x q4; x q5; x q6; x q7; x q8; x q9; x q10; x q11; x q12; x q13; h q13; mcx q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; h q13; x q0; x q1; x q2; x q3; x q4; x q5; x q6; x q7; x q8; x q9; x q10; x q11; x q12; x q13; h q0; h q1; h q2; h q3; h q4; h q5; h q6; h q7; h q8; h q9; h q10; h q11; h q12; h q13; }
gate gate_Q_134450573623216 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450567984912 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450612726736 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450613179392 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450613178720 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450610641456 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450573284016 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450573613808 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450612308544 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450612316800 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450566643056 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450566640752 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450611529984 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450613598832 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450612307104 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450611525472 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450571190224 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450611913744 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450627887856 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450627150720 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450611918448 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450616301616 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450612319536 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450567491184 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450611520192 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450612672592 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450612668656 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450612838640 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450612837296 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450681808128 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450612837632 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450612967408 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450611113904 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450611116592 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450611121440 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450611113088 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450609239632 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450609229264 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450611110976 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450610854016 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450609236656 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450611122160 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450612680416 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450612973312 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450610862656 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450610855840 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450612345536 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450612353792 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450612346160 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450567690624 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450610378592 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450610373504 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450610382480 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450612167568 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450612168912 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450612165792 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450612162816 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450612036544 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450610985808 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450612029440 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450612171696 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450610860688 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450612042832 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450611113520 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450610380080 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450611726064 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450611727120 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450611717424 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450611418752 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450612159840 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450611417888 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450611406272 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450611407520 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450611117792 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450573290640 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450613322432 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450613324352 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450613328144 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450613334528 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450613328624 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450613329152 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450611420816 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450612043744 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450613062256 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450612560928 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450613328576 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450612564528 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450614399776 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450614399152 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450614395264 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450611535120 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450567389424 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450567392928 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450567396624 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450567397200 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450567394848 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450610991184 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450567385488 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450567393360 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450612552672 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
qreg q[14];
qreg flag[1];
creg meas[15];
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
h q[13];
x flag[0];
gate_Q_134450573623216 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450567984912 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450612726736 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450613179392 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450613178720 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450610641456 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450573284016 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450573613808 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450612308544 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450612316800 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450566643056 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450566640752 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450611529984 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450613598832 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450612307104 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450611525472 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450571190224 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450611913744 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450627887856 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450627150720 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450611918448 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450616301616 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450612319536 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450567491184 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450611520192 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450612672592 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450612668656 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450612838640 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450612837296 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450681808128 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450612837632 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450612967408 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450611113904 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450611116592 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450611121440 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450611113088 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450609239632 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450609229264 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450611110976 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450610854016 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450609236656 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450611122160 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450612680416 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450612973312 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450610862656 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450610855840 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450612345536 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450612353792 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450612346160 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450567690624 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450610378592 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450610373504 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450610382480 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450612167568 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450612168912 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450612165792 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450612162816 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450612036544 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450610985808 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450612029440 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450612171696 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450610860688 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450612042832 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450611113520 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450610380080 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450611726064 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450611727120 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450611717424 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450611418752 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450612159840 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450611417888 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450611406272 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450611407520 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450611117792 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450573290640 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450613322432 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450613324352 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450613328144 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450613334528 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450613328624 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450613329152 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450611420816 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450612043744 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450613062256 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450612560928 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450613328576 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450612564528 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450614399776 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450614399152 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450614395264 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450611535120 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450567389424 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450567392928 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450567396624 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450567397200 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450567394848 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450610991184 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450567385488 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450567393360 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450612552672 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
barrier q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
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
measure flag[0] -> meas[14];